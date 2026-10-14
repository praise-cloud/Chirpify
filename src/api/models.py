from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import uuid
from pydantic import BaseModel, Field, field_validator


class EventPayload(BaseModel):
    """
    Schema for an individual analytics event.
    Enforces strict typing, payload boundaries, and idempotency keys.
    """
    event_id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        description="Globally unique identifier for the event (UUIDv4) for idempotency.",
        examples=["550e8400-e29b-41d4-a716-446655440000"]
    )
    tenant_id: str = Field(
        ...,
        min_length=3,
        max_length=64,
        pattern=r"^[a-zA-Z0-9_\-]+$",
        description="SaaS tenant / customer identifier.",
        examples=["tenant_acme_corp"]
    )
    event_type: str = Field(
        ...,
        min_length=2,
        max_length=128,
        pattern=r"^[a-zA-Z0-9_.\-]+$",
        description="Categorized event action (e.g. user.signup, checkout.completed).",
        examples=["user.signup"]
    )
    user_id: Optional[str] = Field(
        default=None,
        max_length=128,
        description="End-user identifier within the tenant platform.",
        examples=["usr_987654"]
    )
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="UTC timestamp when the event occurred."
    )
    properties: Dict[str, Any] = Field(
        default_factory=dict,
        description="Arbitrary event metadata (e.g. page URL, plan name, price).",
        examples=[{"plan": "pro", "mrr": 99.0, "currency": "USD"}]
    )

    @field_validator("properties")
    @classmethod
    def validate_properties_size(cls, v: Dict[str, Any]) -> Dict[str, Any]:
        """Prevent malicious payload bombs by restricting property dictionary keys."""
        if len(v) > 50:
            raise ValueError("Event properties cannot exceed 50 key-value pairs.")
        return v


class EventBatch(BaseModel):
    """
    Schema for batch event ingestion.
    Bounded to 1-100 events to ensure predictable queue latencies and memory safety.
    """
    events: List[EventPayload] = Field(
        ...,
        min_length=1,
        max_length=100,
        description="List of events to be ingested atomically into the queue."
    )


class IngestResponse(BaseModel):
    """Standardized API response for event ingestion."""
    status: str = "accepted"
    events_queued: int
    request_id: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class HealthResponse(BaseModel):
    """Liveness & Readiness health probe schema."""
    status: str
    version: str
    environment: str
    uptime_seconds: float
    dependencies: Dict[str, str] = Field(default_factory=dict)
