import datetime
import uuid

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from classification.classifier import process_and_classify_email
from classification.coworker import handle_chat
from classification.label_map import target_labels_for
from database.db import Base
from database.repository import EmailRepository


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


def _raw(msg_id, subject, body, sender="jane@techcorp.com"):
    return {
        "gmail_message_id": msg_id,
        "thread_id": f"thread_{msg_id}",
        "sender_name": "Jane",
        "sender_email": sender,
        "recipient": "user@gmail.com",
        "subject": subject,
        "date_received": datetime.datetime(2026, 9, 10, 10, 0, 0),
        "body_plain": body,
        "body_html": "",
        "attachments": [],
        "is_read": False,
    }


def test_target_labels_for_urgent_career():
    labels = target_labels_for("URGENT", "CAREER", "ACTION_REQUIRED", "AUTO_CLASSIFIED")
    assert "AI/Urgent" in labels
    assert "AI/Action Required" in labels
    assert "AI/Career" in labels
    assert "AI/Review" not in labels


def test_search_finds_classified_email(db_session):
    process_and_classify_email(
        db_session,
        _raw("msg_c1", "Interview Invitation — Investment Analyst Internship", "Please confirm your attendance for the interview."),
    )
    found = EmailRepository.search_emails(db_session, query="interview", limit=10)
    assert len(found) == 1
    assert found[0].subject.startswith("Interview")


def test_chat_briefing_and_confirm_does_not_need_gmail(db_session, monkeypatch):
    monkeypatch.setattr("classification.coworker.settings.GEMINI_API_KEY", None)
    monkeypatch.setattr("classification.llm_providers.settings.GEMINI_API_KEY", None)
    monkeypatch.setattr("classification.coworker.settings.DRY_RUN", True)
    monkeypatch.setattr("classification.llm_providers.settings.OLLAMA_ENABLED", False)
    monkeypatch.setattr("classification.coworker.polish_coworker_reply", lambda *a, **k: None)
    process_and_classify_email(
        db_session,
        _raw("msg_c2", "Interview Invitation — Investment Analyst Internship", "Please confirm your attendance for the interview."),
    )
    session_id = str(uuid.uuid4())
    brief = handle_chat(db_session, "Thư nào quan trọng?", session_id=session_id)
    assert brief["cards"]
    assert brief["dry_run"] is True

    applied = handle_chat(db_session, "gắn nhãn", session_id=session_id, confirm=True)
    assert "DRY RUN" in applied["reply"] or "DRY RUN đang bật" in applied["reply"]
    assert applied["cards"]
