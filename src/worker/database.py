import logging
from datetime import datetime, timezone
from contextlib import contextmanager
from sqlalchemy import (
    create_engine,
    Column,
    String,
    DateTime,
    Date,
    Integer,
    Boolean,
    JSON,
    UniqueConstraint,
    Index,
)
from sqlalchemy.orm import declarative_base, sessionmaker, scoped_session
from src.api.config import settings

logger = logging.getLogger("chirpify.worker.database")

Base = declarative_base()


class Tenant(Base):
    """Multi-tenant customer account record."""
    __tablename__ = "tenants"

    id = Column(String(64), primary_key=True, index=True)
    name = Column(String(128), nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)


class EventLog(Base):
    """
    Immutable relational event log table.
    Stores individual events for querying, debugging, and auditing.
    """
    __tablename__ = "event_logs"

    event_id = Column(String(64), primary_key=True)
    tenant_id = Column(String(64), index=True, nullable=False)
    event_type = Column(String(128), index=True, nullable=False)
    user_id = Column(String(128), nullable=True, index=True)
    timestamp = Column(DateTime, index=True, nullable=False)
    properties = Column(JSON, default=dict, nullable=False)
    ingested_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    __table_args__ = (
        Index("idx_tenant_event_time", "tenant_id", "event_type", "timestamp"),
    )


class DailyEventAggregate(Base):
    """
    Pre-aggregated daily event counts for rapid dashboard queries.
    Prevents running expensive COUNT(*) queries across millions of raw rows.
    """
    __tablename__ = "daily_event_aggregates"

    id = Column(Integer, primary_key=True, autoincrement=True)
    tenant_id = Column(String(64), nullable=False)
    event_type = Column(String(128), nullable=False)
    event_date = Column(Date, nullable=False)
    total_count = Column(Integer, default=1, nullable=False)
    unique_users = Column(Integer, default=1, nullable=False)

    __table_args__ = (
        UniqueConstraint("tenant_id", "event_type", "event_date", name="uq_tenant_event_date"),
        Index("idx_aggregate_lookup", "tenant_id", "event_date"),
    )


# Database Engine with production connection pooling
engine = None
SessionLocal = None


def get_engine():
    global engine, SessionLocal
    if engine is None:
        engine = create_engine(
            settings.database_url,
            pool_size=10,
            max_overflow=20,
            pool_recycle=1800,
            pool_pre_ping=True,  # Proactively test connection liveness
            echo=settings.DEBUG,
        )
        SessionLocal = scoped_session(sessionmaker(autocommit=False, autoflush=False, bind=engine))
    return engine


@contextmanager
def get_db_session():
    """Context manager for safe transactional database sessions."""
    get_engine()
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def init_db(target_engine=None):
    """Initialize database schemas (used in startup & tests)."""
    eng = target_engine or get_engine()
    Base.metadata.create_all(bind=eng)
    logger.info("Database schemas verified and initialized successfully.")
