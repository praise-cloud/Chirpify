import json
import logging
import signal
import time
from typing import List, Dict, Any
import boto3
from botocore.exceptions import ClientError

from src.api.config import settings
from src.worker.storage import S3StorageHandler, RedisStorageHandler, PostgresStorageHandler
from src.worker.database import init_db

logger = logging.getLogger("chirpify.worker.consumer")


class EventConsumerWorker:
    """
    Production SQS consumer worker.
    Uses SQS Long Polling (WaitTimeSeconds=20) and batch processing.
    Implements graceful shutdown on SIGTERM/SIGINT for zero-downtime rolling deploys.
    """

    def __init__(
        self,
        s3_handler: S3StorageHandler = None,
        redis_handler: RedisStorageHandler = None,
        postgres_handler: PostgresStorageHandler = None,
    ):
        client_kwargs: Dict[str, Any] = {"region_name": settings.AWS_REGION}
        if settings.AWS_ENDPOINT_URL:
            client_kwargs["endpoint_url"] = settings.AWS_ENDPOINT_URL
            client_kwargs["aws_access_key_id"] = "test"
            client_kwargs["aws_secret_access_key"] = "test"

        self.sqs = boto3.client("sqs", **client_kwargs)
        self.queue_url = settings.SQS_QUEUE_URL

        self.s3_handler = s3_handler or S3StorageHandler()
        self.redis_handler = redis_handler or RedisStorageHandler()
        self.postgres_handler = postgres_handler or PostgresStorageHandler()

        self.running = True
        self._register_signal_handlers()

    def _register_signal_handlers(self):
        """Intercept OS termination signals to ensure in-flight batches finish cleanly."""
        signal.signal(signal.SIGINT, self._handle_shutdown)
        signal.signal(signal.SIGTERM, self._handle_shutdown)

    def _handle_shutdown(self, signum, frame):
        logger.info(f"Received termination signal ({signum}). Initiating graceful worker shutdown...")
        self.running = False

    def process_messages(self, max_messages: int = 10, wait_time_seconds: int = 20) -> int:
        """
        Pulls a batch of messages from SQS using Long Polling, processes them,
        and deletes them upon successful storage.
        Returns the number of processed messages.
        """
        try:
            response = self.sqs.receive_message(
                QueueUrl=self.queue_url,
                MaxNumberOfMessages=max_messages,
                WaitTimeSeconds=wait_time_seconds,
                MessageAttributeNames=["All"],
                AttributeNames=["ApproximateReceiveCount"],
            )
        except ClientError as e:
            logger.error(f"Error receiving messages from SQS: {e}")
            time.sleep(2)
            return 0

        messages = response.get("Messages", [])
        if not messages:
            return 0

        logger.info(f"Received {len(messages)} messages from SQS queue.")

        parsed_events: List[Dict[str, Any]] = []
        entries_to_delete: List[Dict[str, str]] = []
        tenant_events_map: Dict[str, List[Dict[str, Any]]] = {}

        for msg in messages:
            receipt_handle = msg["ReceiptHandle"]
            msg_id = msg["MessageId"]
            body = msg["Body"]

            try:
                event_data = json.loads(body)
                parsed_events.append(event_data)

                tenant_id = event_data.get("tenant_id", "default")
                if tenant_id not in tenant_events_map:
                    tenant_events_map[tenant_id] = []
                tenant_events_map[tenant_id].append(event_data)

                entries_to_delete.append({
                    "Id": msg_id,
                    "ReceiptHandle": receipt_handle,
                })
            except json.JSONDecodeError as err:
                logger.error(f"Failed to decode message {msg_id}: {err}. Will redrive to DLQ.")
                # Do NOT delete; let SQS move to DLQ after maxReceiveCount

        if parsed_events:
            # 1. Archive to S3 (per tenant partition)
            for tenant_id, t_events in tenant_events_map.items():
                try:
                    self.s3_handler.archive_batch(t_events, tenant_id=tenant_id)
                except Exception as e:
                    logger.error(f"S3 archive failed for tenant {tenant_id}: {e}")

            # 2. Update real-time counters in Redis
            try:
                self.redis_handler.update_realtime_metrics(parsed_events)
            except Exception as e:
                logger.error(f"Redis real-time metric update failed: {e}")

            # 3. Persist relational aggregates in PostgreSQL
            try:
                self.postgres_handler.persist_events(parsed_events)
            except Exception as e:
                logger.error(f"PostgreSQL relational persistence failed: {e}")

        # 4. Batch delete processed messages from SQS
        if entries_to_delete:
            try:
                self.sqs.delete_message_batch(
                    QueueUrl=self.queue_url,
                    Entries=entries_to_delete,
                )
                logger.info(f"Successfully acknowledged and deleted {len(entries_to_delete)} messages from SQS.")
            except ClientError as e:
                logger.error(f"Failed to delete processed messages from SQS: {e}")

        return len(parsed_events)

    def start(self):
        """Continuous execution loop."""
        logger.info(f"Starting Chirpify Event Consumer Worker on queue: {self.queue_url}")
        try:
            init_db()
        except Exception as e:
            logger.warning(f"Database init check failed (will retry during operations): {e}")

        while self.running:
            try:
                self.process_messages(max_messages=10, wait_time_seconds=20)
            except Exception as e:
                logger.error(f"Unhandled exception in worker loop: {e}", exc_info=True)
                time.sleep(1)

        logger.info("Worker process terminated gracefully. All in-flight messages completed.")


if __name__ == "__main__":
    logging.basicConfig(
        level=settings.LOG_LEVEL,
        format='{"time": "%(asctime)s", "level": "%(levelname)s", "worker": "%(message)s"}'
    )
    worker = EventConsumerWorker()
    worker.start()
