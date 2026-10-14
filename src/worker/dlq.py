import logging
from typing import Dict, Any, List
import boto3
from botocore.exceptions import ClientError
from src.api.config import settings

logger = logging.getLogger("chirpify.worker.dlq")


class DeadLetterQueueManager:
    """
    Site Reliability Engineering (SRE) tool for Dead Letter Queue (DLQ) operations.
    Supports inspecting failed poison-pill messages and redriving them to the main
    queue after downstream bug fixes or schema updates.
    """

    def __init__(self, dlq_name: str = "chirpify-events-dlq"):
        client_kwargs: Dict[str, Any] = {"region_name": settings.AWS_REGION}
        if settings.AWS_ENDPOINT_URL:
            client_kwargs["endpoint_url"] = settings.AWS_ENDPOINT_URL
            client_kwargs["aws_access_key_id"] = "test"
            client_kwargs["aws_secret_access_key"] = "test"

        self.sqs = boto3.client("sqs", **client_kwargs)
        self.dlq_name = dlq_name
        self._dlq_url = None

    @property
    def dlq_url(self) -> str:
        if self._dlq_url is None:
            try:
                response = self.sqs.get_queue_url(QueueName=self.dlq_name)
                self._dlq_url = response["QueueUrl"]
            except ClientError as e:
                logger.error(f"Failed to resolve DLQ URL for {self.dlq_name}: {e}")
                raise
        return self._dlq_url

    def get_dlq_depth(self) -> int:
        """Returns the number of messages currently quarantined in the DLQ."""
        try:
            attrs = self.sqs.get_queue_attributes(
                QueueUrl=self.dlq_url,
                AttributeNames=["ApproximateNumberOfMessages"],
            )
            return int(attrs["Attributes"].get("ApproximateNumberOfMessages", 0))
        except ClientError as e:
            logger.error(f"Failed to get DLQ depth: {e}")
            return 0

    def inspect_messages(self, max_count: int = 10) -> List[Dict[str, Any]]:
        """Peek into quarantined DLQ messages without deleting them."""
        try:
            response = self.sqs.receive_message(
                QueueUrl=self.dlq_url,
                MaxNumberOfMessages=min(max_count, 10),
                VisibilityTimeout=10,  # Brief visibility timeout so they become visible again
                MessageAttributeNames=["All"],
                AttributeNames=["All"],
            )
            return response.get("Messages", [])
        except ClientError as e:
            logger.error(f"Failed to inspect DLQ: {e}")
            return []

    def redrive_messages(self, target_queue_url: str = None) -> int:
        """
        Redrives messages from the DLQ back to the main processing queue.
        Returns the number of redriven messages.
        """
        dest_url = target_queue_url or settings.SQS_QUEUE_URL
        redriven_count = 0

        while True:
            response = self.sqs.receive_message(
                QueueUrl=self.dlq_url,
                MaxNumberOfMessages=10,
                WaitTimeSeconds=1,
            )
            messages = response.get("Messages", [])
            if not messages:
                break

            for msg in messages:
                # Forward to target queue
                self.sqs.send_message(
                    QueueUrl=dest_url,
                    MessageBody=msg["Body"],
                )
                # Remove from DLQ
                self.sqs.delete_message(
                    QueueUrl=self.dlq_url,
                    ReceiptHandle=msg["ReceiptHandle"],
                )
                redriven_count += 1

        logger.info(f"Redrove {redriven_count} messages from {self.dlq_name} to {dest_url}")
        return redriven_count
