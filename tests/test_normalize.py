import pytest
from processing.normalize import normalize_email_body

def test_normalize_email_body_strips_signatures_and_quotes():
    raw_email = """
    Hi Minh,

    We would like to invite you to an interview on September 15 at 10:00 AM.
    
    On Mon, Sep 8, 2026, John Doe <john@company.com> wrote:
    > Looking forward to discussing your application.

    --
    Best regards,
    Recruiting Team
    Company X
    Unsubscribe from future updates
    """

    cleaned = normalize_email_body(raw_email)
    assert "invite you to an interview" in cleaned
    assert "September 15 at 10:00 AM" in cleaned
    assert "John Doe" not in cleaned
    assert "Unsubscribe" not in cleaned
