import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from database.db import Base
from classification.classifier import process_and_classify_email

TEST_DATABASE_URL = "sqlite:///:memory:"

@pytest.fixture
def db_session():
    engine = create_engine(TEST_DATABASE_URL, connect_args={"check_same_thread": False})
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()

def test_career_interview_email_classification(db_session):
    raw_email = {
        "gmail_message_id": "msg_001",
        "thread_id": "thread_001",
        "sender_name": "Recruiter Jane",
        "sender_email": "jane@techcorp.com",
        "recipient": "user@gmail.com",
        "subject": "Interview Invitation — Investment Analyst Internship",
        "date_received": "2026-09-10T10:00:00Z",
        "body_plain": "We would like to invite you to an interview on September 15 at 10:00 AM. Please confirm your attendance.",
        "body_html": "",
        "attachments": [],
        "is_read": False
    }
    
    # Fix date string conversion for fixture test
    import datetime
    raw_email["date_received"] = datetime.datetime(2026, 9, 10, 10, 0, 0)

    result = process_and_classify_email(db_session, raw_email)
    
    assert result["category"] == "CAREER"
    assert result["priority"] in ["URGENT", "IMPORTANT"]
    assert result["action_status"] == "ACTION_REQUIRED"

def test_promotional_email_classification(db_session):
    import datetime
    raw_email = {
        "gmail_message_id": "msg_002",
        "thread_id": "thread_002",
        "sender_name": "MegaStore",
        "sender_email": "deals@megastore.com",
        "recipient": "user@gmail.com",
        "subject": "20% OFF Everything This Weekend!",
        "date_received": datetime.datetime(2026, 9, 10, 10, 0, 0),
        "body_plain": "Don't miss our mega clearance sale. Unsubscribe from future deals.",
        "body_html": "",
        "attachments": [],
        "is_read": False
    }

    result = process_and_classify_email(db_session, raw_email)
    
    assert result["category"] == "PROMOTION"
    assert result["priority"] == "LOW_PRIORITY"
    assert result["action_status"] == "NO_ACTION"
