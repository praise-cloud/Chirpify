import time
import uuid
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, Response, status, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from src.api.config import settings
from src.api.models import (
    EventPayload,
    EventBatch,
    IngestResponse,
    HealthResponse
)
from src.api.queue import QueueProducer, get_queue_producer

# Configure structured logging
logging.basicConfig(
    level=settings.LOG_LEVEL,
    format='{"time": "%(asctime)s", "level": "%(levelname)s", "name": "%(name)s", "message": "%(message)s"}'
)
logger = logging.getLogger("chirpify.api")

# Track application start time for uptime metric
START_TIME = time.time()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle management for startup and graceful shutdown."""
    logger.info(f"Starting {settings.APP_NAME} v{settings.APP_VERSION} [{settings.ENVIRONMENT}]")
    yield
    logger.info("Gracefully shutting down Chirpify Ingestion API...")


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="High-throughput real-time event analytics ingestion API.",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS Middleware (configurable for production environments)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if settings.ENVIRONMENT == "development" else [],
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)


@app.middleware("http")
async def add_observability_headers(request: Request, call_next):
    """
    Middleware injecting correlation IDs (X-Request-ID) and processing latency (X-Process-Time).
    Critical for distributed tracing and SRE monitoring.
    """
    request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
    start_time = time.time()

    # Pass request_id through request state
    request.state.request_id = request_id

    response: Response = await call_next(request)

    process_time = time.time() - start_time
    response.headers["X-Request-ID"] = request_id
    response.headers["X-Process-Time"] = f"{process_time:.4f}s"

    logger.info(
        f'{{"method": "{request.method}", "path": "{request.url.path}", '
        f'"status": {response.status_code}, "latency": {process_time:.4f}, '
        f'"request_id": "{request_id}"}}'
    )
    return response


# Dependency injection for queue producer
def get_producer() -> QueueProducer:
    return get_queue_producer()


@app.get(
    "/healthz",
    response_model=HealthResponse,
    tags=["Observability"],
    summary="Liveness Probe"
)
async def liveness_probe():
    """
    K8s / Fargate Liveness Probe.
    Returns 200 if the web process is alive and responding.
    """
    return HealthResponse(
        status="healthy",
        version=settings.APP_VERSION,
        environment=settings.ENVIRONMENT,
        uptime_seconds=round(time.time() - START_TIME, 2),
        dependencies={"process": "alive"}
    )


@app.get(
    "/readyz",
    response_model=HealthResponse,
    tags=["Observability"],
    summary="Readiness Probe"
)
async def readiness_probe(producer: QueueProducer = Depends(get_producer)):
    """
    K8s / Fargate Readiness Probe.
    Returns 200 if downstream buffer (SQS) is accessible; returns 503 if degraded.
    """
    queue_ok = producer.is_healthy()
    status_str = "ready" if queue_ok else "degraded"
    status_code = status.HTTP_200_OK if queue_ok else status.HTTP_503_SERVICE_UNAVAILABLE

    return JSONResponse(
        status_code=status_code,
        content=HealthResponse(
            status=status_str,
            version=settings.APP_VERSION,
            environment=settings.ENVIRONMENT,
            uptime_seconds=round(time.time() - START_TIME, 2),
            dependencies={
                "queue": "connected" if queue_ok else "unreachable"
            }
        ).model_dump()
    )


@app.post(
    "/api/v1/events",
    response_model=IngestResponse,
    status_code=status.HTTP_202_ACCEPTED,
    tags=["Ingestion"],
    summary="Ingest Single Event"
)
async def ingest_event(
    event: EventPayload,
    request: Request,
    producer: QueueProducer = Depends(get_producer)
):
    """
    Ingest a single user action/event asynchronously.
    Returns 202 Accepted immediately upon buffering into SQS.
    """
    try:
        producer.send_event(event)
        return IngestResponse(
            status="accepted",
            events_queued=1,
            request_id=request.state.request_id
        )
    except Exception as e:
        logger.error(f"Event ingestion failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to buffer event into ingestion queue"
        )


@app.post(
    "/api/v1/events/batch",
    response_model=IngestResponse,
    status_code=status.HTTP_202_ACCEPTED,
    tags=["Ingestion"],
    summary="Ingest Batch of Events"
)
async def ingest_event_batch(
    batch: EventBatch,
    request: Request,
    producer: QueueProducer = Depends(get_producer)
):
    """
    Ingest a batch of events (1-100 items) in a single request.
    Optimizes network calls using SQS batching.
    """
    try:
        count = producer.send_batch(batch.events)
        return IngestResponse(
            status="accepted",
            events_queued=count,
            request_id=request.state.request_id
        )
    except Exception as e:
        logger.error(f"Batch ingestion failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to buffer event batch into ingestion queue"
        )
