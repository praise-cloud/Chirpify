import gzip
import json
import uuid
import logging
from datetime import datetime, timezone
from typing import List, Dict, Any
import boto3
import redis
from botocore.exceptions import ClientError
from sqlalchemy.dialects.postgresql import insert as pg_insert

from src.api.config import settings
from src.worker.database import get_db_session, EventLog, DailyEventAggregate

logger = logging.getLogger("chirpify.worker.storage")


class S3StorageHandler:
    """
    Archives raw event batches to S3 (or LocalStack S3) as compressed JSON.gz.
    Organized into standard date partitions for query engines (Athena/DuckDB/Glue).
    Partition schema: events/year=YYYY/month=MM/day=DD/tenant_id=.../batch_<uuid>.json.gz
    """

    def __init__(self, bucket_name: str = "chirpify-raw-events-bucket"):
        self.bucket_name = bucket_name
        client_kwargs: Dict[str, Any] = {"region_name": settings.AWS_REGION}
        if settings.AWS_ENDPOINT_URL:
            client_kwargs["endpoint_url"] = settings.AWS_ENDPOINT_URL
            client_kwargs["aws_access_key_id"] = "test"
            client_kwargs["aws_secret_access_key"] = "test"

        self.s3 = boto3.client("s3", **client_kwargs)

    def archive_batch(self, events: List[Dict[str, Any]], tenant_id: str) -> str:
        """
        Compresses and uploads a batch of events to S3.
        Returns the resulting S3 object key.
        """
        if not events:
            return ""

        now = datetime.now(timezone.utc)
        batch_id = str(uuid.uuid4())
        key = (
            f"events/year={now.year}/month={now.month:02d}/day={now.day:02d}/"
            f"tenant={tenant_id}/batch_{batch_id}.json.gz"
        )

        serialized_data = json.dumps(events).encode("utf-8")
        compressed_data = gzip.compress(serialized_data)

        try:
            self.s3.put_object(
                Bucket=self.bucket_name,
                Key=key,
                Body=compressed_data,
                ContentType="application/json",
                ContentEncoding="gzip",
                Metadata={
                    "tenant_id": tenant_id,
                    "event_count": str(len(events)),
                    "archived_at": now.isoformat(),
                },
            )
            logger.info(f"Archived {len(events)} events to s3://{self.bucket_name}/{key}")
            return key
        except ClientError as e:
            logger.error(f"Failed to upload raw event batch to S3: {e}")
            raise


class RedisStorageHandler:
    """
    Sub-millisecond real-time analytics counter using Redis.
    Uses Hash Maps for categorical event counters and HyperLogLog (PFADD)
    for memory-efficient unique user cardinality (DAU) estimation.
    """

    def __init__(self):
        self.client = redis.Redis(
            host=settings.REDIS_HOST,
            port=settings.REDIS_PORT,
            db=settings.REDIS_DB,
            decode_responses=True,
            socket_timeout=3,
        )

    def update_realtime_metrics(self, events: List[Dict[str, Any]], ttl_days: int = 30):
        """
        Updates real-time counters atomically using a Redis pipeline.
        TTL is set on all keys to prevent unbounded memory growth.
        """
        if not events:
            return

        pipeline = self.client.pipeline()
        ttl_seconds = ttl_days * 86400

        for event in events:
            tenant_id = event.get("tenant_id", "unknown")
            event_type = event.get("event_type", "generic")
            user_id = event.get("user_id")
            event_time_str = event.get("timestamp")

            if event_time_str:
                dt = datetime.fromisoformat(event_time_str)
            else:
                dt = datetime.now(timezone.utc)

            date_str = dt.strftime("%Y-%m-%d")

            # 1. Event Type Counter within Hash Map
            hash_key = f"chirpify:tenant:{tenant_id}:{date_str}:events"
            pipeline.hincrby(hash_key, event_type, 1)
            pipeline.expire(hash_key, ttl_seconds)

            # 2. Total Daily Events
            total_key = f"chirpify:tenant:{tenant_id}:{date_str}:total"
            pipeline.incr(total_key)
            pipeline.expire(total_key, ttl_seconds)

            # 3. Daily Active Users (DAU) using HyperLogLog (PFADD)
            if user_id:
                dau_key = f"chirpify:tenant:{tenant_id}:{date_str}:dau"
                pipeline.pfadd(dau_key, str(user_id))
                pipeline.expire(dau_key, ttl_seconds)

        pipeline.execute()
        logger.info(f"Updated real-time Redis metrics for {len(events)} events via pipeline.")

    def get_realtime_event_counts(self, tenant_id: str, date_str: str) -> Dict[str, int]:
        """Fetch all real-time event counts for a tenant on a specific day."""
        hash_key = f"chirpify:tenant:{tenant_id}:{date_str}:events"
        data = self.client.hgetall(hash_key)
        return {k: int(v) for k, v in data.items()}

    def get_daily_active_users(self, tenant_id: str, date_str: str) -> int:
        """Fetch estimated unique active users using HyperLogLog (PFCOUNT)."""
        dau_key = f"chirpify:tenant:{tenant_id}:{date_str}:dau"
        return self.client.pfcount(dau_key)


class PostgresStorageHandler:
    """
    Relational persistence handler using PostgreSQL.
    Stores raw events with duplicate suppression (idempotency)
    and aggregates daily counts.
    """

    def persist_events(self, events: List[Dict[str, Any]]):
        """Persists individual event records and updates daily aggregates atomically."""
        if not events:
            return

        with get_db_session() as session:
            for event in events:
                event_id = event["event_id"]
                tenant_id = event["tenant_id"]
                event_type = event["event_type"]
                user_id = event.get("user_id")

                ts = event.get("timestamp")
                if isinstance(ts, str):
                    event_dt = datetime.fromisoformat(ts)
                elif isinstance(ts, datetime):
                    event_dt = ts
                else:
                    event_dt = datetime.now(timezone.utc)

                event_date = event_dt.date()

                # 1. Insert EventLog (check if exists for idempotency)
                existing = session.query(EventLog).filter_by(event_id=event_id).first()
                if not existing:
                    event_record = EventLog(
                        event_id=event_id,
                        tenant_id=tenant_id,
                        event_type=event_type,
                        user_id=user_id,
                        timestamp=event_dt,
                        properties=event.get("properties", {}),
                    )
                    session.add(event_record)

                # 2. Upsert Daily Event Aggregate
                # Try Postgres ON CONFLICT if engine is PostgreSQL, fallback to standard SQL for SQLite/tests
                is_postgres = session.bind.dialect.name == "postgresql"
                if is_postgres:
                    stmt = pg_insert(DailyEventAggregate).values(
                        tenant_id=tenant_id,
                        event_type=event_type,
                        event_date=event_date,
                        total_count=1,
                        unique_users=1,
                    )
                    stmt = stmt.on_conflict_do_update(
                        constraint="uq_tenant_event_date",
                        set_={"total_count": DailyEventAggregate.total_count + 1},
                    )
                    session.execute(stmt)
                else:
                    # SQLite/generic fallback for unit tests
                    agg = (
                        session.query(DailyEventAggregate)
                        .filter_by(tenant_id=tenant_id, event_type=event_type, event_date=event_date)
                        .first()
                    )
                    if agg:
                        agg.total_count += 1
                    else:
                        new_agg = DailyEventAggregate(
                            tenant_id=tenant_id,
                            event_type=event_type,
                            event_date=event_date,
                            total_count=1,
                            unique_users=1,
                        )
                        session.add(new_agg)

        logger.info(f"Persisted {len(events)} events to PostgreSQL database.")
