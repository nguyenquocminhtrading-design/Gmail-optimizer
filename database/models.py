import datetime
from sqlalchemy import (
    Column, Integer, String, Text, Boolean, Float, DateTime, ForeignKey, Index
)
from sqlalchemy.orm import relationship
from database.db import Base

class EmailModel(Base):
    __tablename__ = "emails"

    id = Column(Integer, primary_key=True, index=True)
    gmail_message_id = Column(String(100), unique=True, index=True, nullable=False)
    thread_id = Column(String(100), index=True, nullable=False)
    sender_name = Column(String(255), nullable=True)
    sender_email = Column(String(255), index=True, nullable=False)
    recipient = Column(String(255), nullable=True)
    subject = Column(Text, nullable=True)
    date_received = Column(DateTime, nullable=False, index=True)
    body_plain = Column(Text, nullable=True)
    body_html = Column(Text, nullable=True)
    normalized_body = Column(Text, nullable=True)
    is_read = Column(Boolean, default=False)
    has_attachments = Column(Boolean, default=False)
    existing_labels = Column(Text, nullable=True) # Comma separated or JSON string
    processed_at = Column(DateTime, default=datetime.datetime.utcnow)

    # Relationships
    classification = relationship("ClassificationModel", back_populates="email", uselist=False, cascade="all, delete-orphan")
    deadlines = relationship("DeadlineModel", back_populates="email", cascade="all, delete-orphan")
    actions = relationship("ActionModel", back_populates="email", cascade="all, delete-orphan")
    attachments = relationship("AttachmentModel", back_populates="email", cascade="all, delete-orphan")
    feedbacks = relationship("UserFeedbackModel", back_populates="email", cascade="all, delete-orphan")


class ClassificationModel(Base):
    __tablename__ = "classifications"

    id = Column(Integer, primary_key=True, index=True)
    email_id = Column(Integer, ForeignKey("emails.id"), unique=True, nullable=False)
    priority = Column(String(50), nullable=False)     # URGENT, IMPORTANT, NORMAL, LOW_PRIORITY
    action_status = Column(String(50), nullable=False) # ACTION_REQUIRED, WAITING_FOR_REPLY, NO_ACTION, FOLLOW_UP
    category = Column(String(50), nullable=False)      # WORK, UNIVERSITY, CAREER, FINANCE, BANKING, PERSONAL, NEWSLETTER, PROMOTION, RECEIPT, MEETING, DOCUMENT, OTHER
    importance_score = Column(Float, default=0.0)      # 0 to 100
    confidence = Column(Float, default=0.0)            # 0.0 to 1.0
    status = Column(String(50), default="NEEDS_REVIEW")# AUTO_CLASSIFIED, NEEDS_REVIEW, USER_REVIEWED
    reasons_json = Column(Text, nullable=True)         # JSON list of string explanations
    model_version = Column(String(50), default="v1.0")
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    email = relationship("EmailModel", back_populates="classification")


class DeadlineModel(Base):
    __tablename__ = "deadlines"

    id = Column(Integer, primary_key=True, index=True)
    email_id = Column(Integer, ForeignKey("emails.id"), nullable=False)
    title = Column(String(255), nullable=False)
    deadline_date = Column(DateTime, nullable=False, index=True)
    is_relative = Column(Boolean, default=False)
    confidence = Column(Float, default=0.0)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    email = relationship("EmailModel", back_populates="deadlines")


class ActionModel(Base):
    __tablename__ = "actions"

    id = Column(Integer, primary_key=True, index=True)
    email_id = Column(Integer, ForeignKey("emails.id"), nullable=False)
    action_description = Column(Text, nullable=False)
    priority = Column(String(50), default="NORMAL")
    is_completed = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    email = relationship("EmailModel", back_populates="actions")


class AttachmentModel(Base):
    __tablename__ = "attachments"

    id = Column(Integer, primary_key=True, index=True)
    email_id = Column(Integer, ForeignKey("emails.id"), nullable=False)
    filename = Column(String(255), nullable=False)
    mime_type = Column(String(100), nullable=True)
    size_bytes = Column(Integer, default=0)
    relevance_category = Column(String(50), default="OTHER") # FINANCIAL, CONTRACT, REPORT, IMAGE, OTHER

    email = relationship("EmailModel", back_populates="attachments")


class UserFeedbackModel(Base):
    __tablename__ = "user_feedback"

    id = Column(Integer, primary_key=True, index=True)
    email_id = Column(Integer, ForeignKey("emails.id"), nullable=False)
    old_priority = Column(String(50), nullable=True)
    new_priority = Column(String(50), nullable=False)
    old_category = Column(String(50), nullable=True)
    new_category = Column(String(50), nullable=False)
    old_action = Column(String(50), nullable=True)
    new_action = Column(String(50), nullable=False)
    scope = Column(String(50), default="THIS_EMAIL") # THIS_EMAIL, THIS_SENDER, SIMILAR_SUBJECTS
    reason = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    email = relationship("EmailModel", back_populates="feedbacks")


class RuleModel(Base):
    __tablename__ = "rules"

    id = Column(Integer, primary_key=True, index=True)
    rule_type = Column(String(50), default="LEARNED_PREFERENCE") # HARD_OVERRIDE, LEARNED_PREFERENCE
    condition_type = Column(String(50), nullable=False)          # SENDER, SUBJECT_CONTAINS, KEYWORD
    condition_value = Column(String(255), nullable=False, index=True)
    target_priority = Column(String(50), nullable=True)
    target_category = Column(String(50), nullable=True)
    target_action = Column(String(50), nullable=True)
    never_archive = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)


class SyncStateModel(Base):
    __tablename__ = "sync_state"

    id = Column(Integer, primary_key=True)
    last_history_id = Column(String(100), nullable=True)
    last_sync_timestamp = Column(DateTime, default=datetime.datetime.utcnow)
    total_synced_count = Column(Integer, default=0)


class ChatSessionModel(Base):
    __tablename__ = "chat_sessions"

    id = Column(String(64), primary_key=True)
    pending_email_ids = Column(Text, default="[]")
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

    messages = relationship("ChatMessageModel", back_populates="session", cascade="all, delete-orphan")


class ChatMessageModel(Base):
    __tablename__ = "chat_messages"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String(64), ForeignKey("chat_sessions.id"), nullable=False, index=True)
    role = Column(String(20), nullable=False)  # user, assistant
    content = Column(Text, nullable=False)
    cards_json = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    session = relationship("ChatSessionModel", back_populates="messages")
