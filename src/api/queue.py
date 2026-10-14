import logging
from abc import ABC, abstractmethod
from typing import List, Dict, Any
import boto3
from botocore.exceptions import ClientError
from src.api.models import EventPayload
from src.api.config import settings

logger = logging.getLogger(__name__)


class QueueProducer(ABC):
    """Abstract interface for queue producers (enables decoupling and testability)."""

    @abstractmethod
    def send_event(self, event: EventPayload) -> bool:
        """Publish a single event to the queue."""
        pass

    @abstractmethod
    def send_batch(self, events: List[EventPayload]) -> int:
        """
        Publish a batch of events.
        Returns the number of successfully enqueued events.
        """
        pass

    @abstractmethod
    def is_healthy(self) -> bool:
        """Health check for readiness probe."""
        pass


class SQSQueueProducer(QueueProducer):
    """
    AWS SQS producer supporting standard AWS SQS and LocalStack.
    Optimized with chunked batch sending (up to 10 messages per SQS API call).
    """

    def __init__(self):
        client_kwargs: Dict[str, Any] = {
            "region_name": settings.AWS_REGION
        }
        if settings.AWS_ENDPOINT_URL:
            client_kwargs["endpoint_url"] = settings.AWS_ENDPOINT_URL
            client_kwargs["aws_access_key_id"] = "test"
            client_kwargs["aws_secret_access_key"] = "test"

        self.sqs = boto3.client("sqs", **client_kwargs)
        self.queue_url = settings.SQS_QUEUE_URL

    def send_event(self, event: EventPayload) -> bool:
        try:
            payload_json = event.model_dump_json()
            self.sqs.send_message(
                QueueUrl=self.queue_url,
                MessageBody=payload_json,
                MessageAttributes={
                    "TenantId": {
                        "DataType": "String",
                        "StringValue": event.tenant_id
                    },
                    "EventType": {
                        "DataType": "String",
                        "StringValue": event.event_type
                    }
                }
            )
            return True
        except ClientError as e:
            logger.error(f"Failed to publish event {event.event_id} to SQS: {e}")
            raise

    def send_batch(self, events: List[EventPayload]) -> int:
        """
        SQS limits batch operations to 10 messages per API call.
        We chunk the batch into slices of 10 to maximize network efficiency.
        """
        successful_count = 0
        chunk_size = 10

        for i in range(0, len(events), chunk_size):
            chunk = events[i : i + chunk_size]
            entries = [
                {
                    "Id": str(idx),
                    "MessageBody": event.model_dump_json(),
                    "MessageAttributes": {
                        "TenantId": {
                            "DataType": "String",
                            "StringValue": event.tenant_id
                        },
                        "EventType": {
                            "DataType": "String",
                            "StringValue": event.event_type
                        }
                    }
                }
                for idx, event in enumerate(chunk)
            ]

            try:
                response = self.sqs.send_message_batch(
                    QueueUrl=self.queue_url,
                    Entries=entries
                )
                successful_count += len(response.get("Successful", []))
                failed = response.get("Failed", [])
                if failed:
                    logger.warning(f"SQS batch send partial failure: {len(failed)} messages failed.")
            except ClientError as e:
                logger.error(f"Failed to publish batch slice to SQS: {e}")
                raise

        return successful_count

    def is_healthy(self) -> bool:
        """Verify connectivity to SQS by inspecting queue attributes."""
        try:
            self.sqs.get_queue_attributes(
                QueueUrl=self.queue_url,
                AttributeNames=["ApproximateNumberOfMessages"]
            )
            return True
        except Exception as e:
            logger.warning(f"SQS health check failed: {e}")
            return False


class MockQueueProducer(QueueProducer):
    """
    In-memory mock queue producer for rapid testing and zero-dependency local dev.
    """

    def __init__(self):
        self.messages: List[Dict[str, Any]] = []

    def send_event(self, event: EventPayload) -> bool:
        self.messages.append(event.model_dump())
        return True

    def send_batch(self, events: List[EventPayload]) -> int:
        for event in events:
            self.messages.append(event.model_dump())
        return len(events)

    def is_healthy(self) -> bool:
        return True

    def clear(self):
        self.messages.clear()


def get_queue_producer() -> QueueProducer:
    """Factory function to provide the configured QueueProducer implementation."""
    if settings.USE_MOCK_QUEUE:
        return MockQueueProducer()
    return SQSQueueProducer()
