import gzip
import json
from datetime import datetime, timezone
from unittest.mock import MagicMock
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, scoped_session

from src.worker.database import EventLog, DailyEventAggregate, init_db
import src.worker.database as db_module
from src.worker.storage import S3StorageHandler, RedisStorageHandler, PostgresStorageHandler
from src.worker.consumer import EventConsumerWorker
from src.worker.dlq import DeadLetterQueueManager


@pytest.fixture
def sqlite_db(monkeypatch):
    """Provide an isolated, in-memory SQLite database for testing SQL models & persistence."""
    test_engine = create_engine("sqlite:///:memory:")
    test_session_factory = scoped_session(sessionmaker(autocommit=False, autoflush=False, bind=test_engine))
    init_db(target_engine=test_engine)

    # Monkeypatch the worker database engine and session
    monkeypatch.setattr(db_module, "engine", test_engine)
    monkeypatch.setattr(db_module, "SessionLocal", test_session_factory)
    yield test_engine


def test_s3_storage_archive_batch():
    """Verify S3StorageHandler compresses batch and partitions key by date and tenant."""
    handler = S3StorageHandler(bucket_name="test-bucket")
    handler.s3 = MagicMock()

    events = [
        {"event_id": "evt-1", "tenant_id": "tenant-corp", "event_type": "user.login"},
        {"event_id": "evt-2", "tenant_id": "tenant-corp", "event_type": "page.view"},
    ]

    key = handler.archive_batch(events, tenant_id="tenant-corp")

    assert "tenant=tenant-corp" in key
    assert key.endswith(".json.gz")
    assert handler.s3.put_object.called

    # Verify put_object arguments
    call_kwargs = handler.s3.put_object.call_args[1]
    assert call_kwargs["Bucket"] == "test-bucket"
    assert call_kwargs["ContentEncoding"] == "gzip"

    # Decompress body to verify original data
    decompressed = json.loads(gzip.decompress(call_kwargs["Body"]).decode("utf-8"))
    assert len(decompressed) == 2
    assert decompressed[0]["event_id"] == "evt-1"


def test_redis_storage_realtime_metrics():
    """Verify RedisStorageHandler pipelines metric increments and HyperLogLog tracking."""
    handler = RedisStorageHandler()
    mock_redis = MagicMock()
    mock_pipeline = MagicMock()
    mock_redis.pipeline.return_value = mock_pipeline
    handler.client = mock_redis

    events = [
        {
            "event_id": "evt-10",
            "tenant_id": "tenant-alpha",
            "event_type": "checkout.complete",
            "user_id": "user-99",
            "timestamp": "2026-05-15T12:00:00+00:00",
        }
    ]

    handler.update_realtime_metrics(events)

    assert mock_pipeline.hincrby.called
    assert mock_pipeline.incr.called
    assert mock_pipeline.pfadd.called
    assert mock_pipeline.execute.called


def test_postgres_storage_persistence_and_idempotency(sqlite_db):
    """Verify relational persistence, aggregation increments, and duplicate event idempotency."""
    handler = PostgresStorageHandler()

    event = {
        "event_id": "evt-uuid-1",
        "tenant_id": "tenant-beta",
        "event_type": "signup",
        "user_id": "usr-1",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "properties": {"role": "admin"},
    }

    # 1. First insertion
    handler.persist_events([event])

    with db_module.get_db_session() as session:
        logs = session.query(EventLog).all()
        assert len(logs) == 1
        assert logs[0].event_id == "evt-uuid-1"

        aggs = session.query(DailyEventAggregate).all()
        assert len(aggs) == 1
        assert aggs[0].total_count == 1

    # 2. Duplicate insertion with same event_id (Idempotency test)
    handler.persist_events([event])

    with db_module.get_db_session() as session:
        logs = session.query(EventLog).all()
        assert len(logs) == 1  # Should still be 1, duplicate ignored!


def test_consumer_worker_process_messages():
    """Verify worker pulls from SQS, invokes storage pipelines, and deletes processed messages."""
    mock_s3 = MagicMock()
    mock_redis = MagicMock()
    mock_postgres = MagicMock()

    worker = EventConsumerWorker(
        s3_handler=mock_s3,
        redis_handler=mock_redis,
        postgres_handler=mock_postgres,
    )
    worker.sqs = MagicMock()

    # Simulate SQS message payload
    message_body = json.dumps({
        "event_id": "evt-sqs-1",
        "tenant_id": "tenant-gamma",
        "event_type": "button.click",
    })

    worker.sqs.receive_message.return_value = {
        "Messages": [
            {
                "MessageId": "msg-12345",
                "ReceiptHandle": "receipt-token-xyz",
                "Body": message_body,
            }
        ]
    }

    processed_count = worker.process_messages(max_messages=10, wait_time_seconds=1)

    assert processed_count == 1
    assert mock_s3.archive_batch.called
    assert mock_redis.update_realtime_metrics.called
    assert mock_postgres.persist_events.called

    # Verify message was deleted from SQS
    assert worker.sqs.delete_message_batch.called
    del_entries = worker.sqs.delete_message_batch.call_args[1]["Entries"]
    assert del_entries[0]["ReceiptHandle"] == "receipt-token-xyz"


def test_dlq_manager_inspection():
    """Verify DLQ manager inspects depth and reads quarantined messages."""
    dlq_mgr = DeadLetterQueueManager(dlq_name="chirpify-events-dlq")
    dlq_mgr.sqs = MagicMock()
    dlq_mgr._dlq_url = "http://localhost:4566/dlq"

    dlq_mgr.sqs.get_queue_attributes.return_value = {
        "Attributes": {"ApproximateNumberOfMessages": "5"}
    }
    dlq_mgr.sqs.receive_message.return_value = {
        "Messages": [{"MessageId": "dlq-msg-1", "Body": "corrupted-json"}]
    }

    assert dlq_mgr.get_dlq_depth() == 5
    messages = dlq_mgr.inspect_messages(max_count=1)
    assert len(messages) == 1
    assert messages[0]["MessageId"] == "dlq-msg-1"
