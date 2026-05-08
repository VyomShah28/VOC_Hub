from sqlalchemy import Column, String, Date, Boolean, Integer, Float, ForeignKey, Text, UniqueConstraint, DateTime
from datetime import datetime
from sqlalchemy.dialects.postgresql import JSONB
from pgvector.sqlalchemy import Vector
from app.db.database import Base


class FeedbackRaw(Base):
    __tablename__ = 'feedback_raw'
    id = Column(String, primary_key=True)
    source = Column(String)
    segment = Column(String)
    customer_id = Column(String)
    date = Column(Date)
    raw_text = Column(String)
    metadata_col = Column("metadata", JSONB)
    processed = Column(Boolean, default=False)


class FeedbackProcessed(Base):
    __tablename__ = 'feedback_processed'
    id = Column(Integer, primary_key=True, autoincrement=True)
    feedback_id = Column(String, ForeignKey('feedback_raw.id'), index=True, nullable=False)
    clean_text = Column(String)
    intents = Column(JSONB)
    sentiment_score = Column(Float, default=0.0)
    urgency_keyword_score = Column(Float, default=0.0)
    arr = Column(Float, default=0.0)
    embedding = Column(Vector(256))


class Theme(Base):
    __tablename__ = 'themes'
    id = Column(Integer, primary_key=True, autoincrement=True)
    intent_bucket = Column(String, nullable=False)
    name = Column(String)
    keywords = Column(JSONB)
    description = Column(String)
    first_seen = Column(Date)
    last_seen = Column(Date)
    item_count = Column(Integer, default=0)
    is_outlier = Column(Boolean, default=False)


class ThemeItem(Base):
    __tablename__ = 'theme_items'
    id = Column(Integer, primary_key=True, autoincrement=True)
    theme_id = Column(Integer, ForeignKey('themes.id'), nullable=False, index=True)
    feedback_id = Column(String, ForeignKey('feedback_raw.id'), nullable=False, index=True)


class ThemeWeeklyCount(Base):
    __tablename__ = 'theme_weekly_counts'
    id = Column(Integer, primary_key=True, autoincrement=True)
    theme_id = Column(Integer, ForeignKey('themes.id', ondelete='CASCADE'), nullable=False, index=True)
    week_start = Column(Date, nullable=False)  # Always Monday of that ISO week
    count = Column(Integer, default=0)

    __table_args__ = (
        UniqueConstraint('theme_id', 'week_start', name='uq_theme_week'),
    )


class Opportunity(Base):
    __tablename__ = 'opportunities'
    id = Column(Integer, primary_key=True, autoincrement=True)
    theme_id = Column(Integer, ForeignKey('themes.id'), nullable=False, index=True)
    intent_bucket = Column(String, nullable=False)
    frequency = Column(Integer, default=0)
    total_arr = Column(Float, default=0.0)
    avg_sentiment = Column(Float, default=0.0)
    avg_urgency = Column(Float, default=0.0)
    avg_source_weight = Column(Float, default=0.0)
    velocity = Column(Float, default=0.0)
    alignment_score = Column(Float, default=None)
    alignment_reason = Column(Text, default=None)
    opportunity_score = Column(Float, default=0.0)
    priority_label = Column(String, default="Medium")
    artifact_bug_ticket = Column(JSONB, default=None)
    artifact_prd = Column(JSONB, default=None)
    outcome_statement = Column(Text, default=None)
    updated_at = Column(Date)


class KnowledgeFile(Base):
    __tablename__ = 'knowledge_files'
    id = Column(Integer, primary_key=True, autoincrement=True)
    filename = Column(String, nullable=False)
    file_size_bytes = Column(Integer, nullable=False)
    file_path = Column(String, nullable=False)
    uploaded_at = Column(DateTime, default=datetime.utcnow)


class KnowledgeChunk(Base):
    __tablename__ = 'knowledge_chunks'
    id = Column(Integer, primary_key=True, autoincrement=True)
    file_id = Column(Integer, ForeignKey('knowledge_files.id', ondelete='CASCADE'), nullable=False, index=True)
    chunk_text = Column(Text, nullable=False)
    embedding = Column(Vector(256))