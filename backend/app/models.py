import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
)
from sqlalchemy.orm import relationship

from app.db import Base


def _uuid() -> str:
    return str(uuid.uuid4())


class User(Base):
    __tablename__ = "users"
    id = Column(String, primary_key=True, default=_uuid)
    email = Column(String, unique=True, nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    subscriptions = relationship("Subscription", back_populates="user")
    tax_plans = relationship("TaxPlan", back_populates="user")
    conversations = relationship("Conversation", back_populates="user")


class Subscription(Base):
    __tablename__ = "subscriptions"
    id = Column(String, primary_key=True, default=_uuid)
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    tier = Column(String, nullable=False, default="basic")  # basic | plus | pro
    is_active = Column(Boolean, default=True)
    started_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="subscriptions")


class TaxPlan(Base):
    __tablename__ = "tax_plans"
    id = Column(String, primary_key=True, default=_uuid)
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    tax_year = Column(Integer, nullable=False)
    filing_status = Column(String, nullable=False, default="single")
    data = Column(JSON, default=dict)  # income, deductions, accounts, etc.

    # --- Plan-aware fields (PRD 4.1) -- Tax Coach must always have these
    # without the user re-explaining their situation. ---
    agi = Column(Float, nullable=True)
    magi = Column(Float, nullable=True)
    marginal_rate = Column(Float, nullable=True)
    confirmed_savings = Column(Float, default=0)
    potential_savings = Column(Float, default=0)
    urgent_observations = Column(JSON, default=list)  # e.g. ["Q4 estimated payment due Jan 15"]
    missing_questionnaire_items = Column(JSON, default=list)  # items affecting savings calcs

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = relationship("User", back_populates="tax_plans")
    strategies = relationship("Strategy", back_populates="tax_plan")


class Strategy(Base):
    __tablename__ = "strategies"
    id = Column(String, primary_key=True, default=_uuid)
    tax_plan_id = Column(String, ForeignKey("tax_plans.id"), nullable=False)
    title = Column(String, nullable=False)
    description = Column(Text, nullable=False)
    why_it_applies = Column(Text, nullable=True)  # PRD 4.1 -- personalized rationale
    status = Column(String, default="potential")  # "confirmed" | "potential"
    estimated_savings = Column(Float, nullable=True)
    citations = Column(JSON, default=list)
    created_at = Column(DateTime, default=datetime.utcnow)

    tax_plan = relationship("TaxPlan", back_populates="strategies")


class TaxConstant(Base):
    """Deterministic bracket / limit tables used by the Scenario Agent's
    calculate_tax_scenario() -- never guessed by the LLM."""

    __tablename__ = "tax_constants"
    id = Column(String, primary_key=True, default=_uuid)
    tax_year = Column(Integer, nullable=False)
    key = Column(String, nullable=False)  # e.g. "401k_employee_limit"
    filing_status = Column(String, nullable=True)
    value = Column(JSON, nullable=False)  # scalar or bracket table
    source_url = Column(String, nullable=True)


class Document(Base):
    """Internally curated knowledge (admin-uploaded), distinct from the
    live, DB-driven source_registry used for official government lookups."""

    __tablename__ = "documents"
    id = Column(String, primary_key=True, default=_uuid)
    title = Column(String, nullable=False)
    source_domain = Column(String, nullable=True)
    published = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    chunks = relationship("DocumentChunk", back_populates="document")


class DocumentChunk(Base):
    __tablename__ = "document_chunks"
    id = Column(String, primary_key=True, default=_uuid)
    document_id = Column(String, ForeignKey("documents.id"), nullable=False)
    content = Column(Text, nullable=False)
    # Portable embedding storage (JSON list of floats). In production on
    # Postgres, migrate this column to pgvector's Vector(n) type for ANN
    # search; the ingestion/query code path stays identical either way.
    embedding = Column(JSON, nullable=True)

    document = relationship("Document", back_populates="chunks")


class SourceRegistry(Base):
    """DB-driven registry of official government sources the RAG Agent may
    query. Adding a source is a row insert -- zero code changes."""

    __tablename__ = "source_registry"
    id = Column(String, primary_key=True, default=_uuid)
    domain = Column(String, nullable=False, unique=True)  # e.g. irs.gov
    description = Column(String, nullable=False)
    scope_tags = Column(JSON, default=list)  # e.g. ["retirement", "business"]
    api_method = Column(String, nullable=False)  # tavily_search | direct_fetch | irs_api
    enabled = Column(Boolean, default=True)
    tier = Column(JSON, default=lambda: ["basic", "plus", "pro"])  # subscriber tiers
    added_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Conversation(Base):
    __tablename__ = "conversations"
    id = Column(String, primary_key=True, default=_uuid)
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="conversations")
    turns = relationship("ConversationTurn", back_populates="conversation")


class ConversationTurn(Base):
    __tablename__ = "conversation_turns"
    id = Column(String, primary_key=True, default=_uuid)
    conversation_id = Column(String, ForeignKey("conversations.id"), nullable=False)
    role = Column(String, nullable=False)  # user | assistant
    content = Column(Text, nullable=False)
    intent = Column(String, nullable=True)  # supervisor's routed intent
    citations = Column(JSON, default=list)
    created_at = Column(DateTime, default=datetime.utcnow)

    conversation = relationship("Conversation", back_populates="turns")


class UsageDaily(Base):
    __tablename__ = "usage_daily"
    id = Column(String, primary_key=True, default=_uuid)
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    date = Column(String, nullable=False)  # YYYY-MM-DD
    message_count = Column(Integer, default=0)


class AuditEvent(Base):
    __tablename__ = "audit_events"
    id = Column(String, primary_key=True, default=_uuid)
    user_id = Column(String, nullable=True)
    conversation_id = Column(String, nullable=True)
    event_type = Column(String, nullable=False)  # e.g. "pii_blocked", "chat_turn"
    payload = Column(JSON, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow)


class ProfessionalReferral(Base):
    __tablename__ = "professional_referrals"
    id = Column(String, primary_key=True, default=_uuid)
    user_id = Column(String, nullable=False)
    conversation_id = Column(String, nullable=True)
    reason = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
