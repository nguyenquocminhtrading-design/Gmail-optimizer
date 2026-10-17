"""
notifications/daily_digest.py
------------------------------
Builds and sends a daily digest email summarising URGENT / IMPORTANT emails.
Sent via Gmail API (same OAuth credentials already in use) - no SMTP needed.
"""

from __future__ import annotations

import base64
import datetime
import logging
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import List, Optional

from googleapiclient.discovery import build
from sqlalchemy.orm import Session

from config import settings
from database.models import EmailModel, ClassificationModel
from gmail.auth import get_saved_credentials

logger = logging.getLogger(__name__)


PRIORITY_BADGE = {
    "URGENT":    '<span style="background:#e53e3e;color:#fff;padding:2px 8px;border-radius:12px;font-size:11px;font-weight:700;">🔴 URGENT</span>',
    "IMPORTANT": '<span style="background:#dd6b20;color:#fff;padding:2px 8px;border-radius:12px;font-size:11px;font-weight:700;">🟠 IMPORTANT</span>',
}


def _build_email_row(email: EmailModel) -> str:
    cls = email.classification
    priority = cls.priority if cls else "IMPORTANT"
    badge = PRIORITY_BADGE.get(priority, "")
    category = cls.category if cls else ""
    action = cls.action_status if cls else ""
    subject = email.subject or "(No Subject)"
    sender = f"{email.sender_name} &lt;{email.sender_email}&gt;" if email.sender_name else email.sender_email
    date_str = email.date_received.strftime("%d/%m %H:%M") if email.date_received else ""

    action_label = ""
    if action == "ACTION_REQUIRED":
        action_label = '<span style="color:#e53e3e;font-weight:600;">Cần hành động</span>'
    elif action == "WAITING_FOR_REPLY":
        action_label = '<span style="color:#3182ce;font-weight:600;">Chờ phản hồi</span>'
    elif action == "FOLLOW_UP":
        action_label = '<span style="color:#805ad5;font-weight:600;">Follow-up</span>'

    return f"""
    <tr style="border-bottom:1px solid #e2e8f0;">
      <td style="padding:12px 8px;vertical-align:top;width:90px;">{badge}</td>
      <td style="padding:12px 8px;vertical-align:top;">
        <div style="font-weight:600;color:#1a202c;margin-bottom:2px;">{subject}</div>
        <div style="color:#718096;font-size:12px;">{sender}</div>
      </td>
      <td style="padding:12px 8px;vertical-align:top;color:#4a5568;font-size:12px;">{category}</td>
      <td style="padding:12px 8px;vertical-align:top;font-size:12px;">{action_label}</td>
      <td style="padding:12px 8px;vertical-align:top;color:#718096;font-size:12px;white-space:nowrap;">{date_str}</td>
    </tr>
    """


def build_digest_html(emails: List[EmailModel], report_date: datetime.date) -> str:
    date_label = report_date.strftime("%d/%m/%Y")
    urgent = [e for e in emails if e.classification and e.classification.priority == "URGENT"]
    important = [e for e in emails if e.classification and e.classification.priority == "IMPORTANT"]

    rows_html = "".join(_build_email_row(e) for e in emails)
    if not emails:
        rows_html = """<tr><td colspan="5" style="padding:32px;text-align:center;color:#718096;">
          Khong co email quan trong nao hom nay. Hop thu sach!
        </td></tr>"""

    now_str = datetime.datetime.now().strftime("%H:%M")
    return f"""<!DOCTYPE html>
<html lang="vi"><head><meta charset="UTF-8">
<title>Daily Digest {date_label}</title></head>
<body style="margin:0;padding:0;background:#f7fafc;font-family:Arial,sans-serif;">
<div style="max-width:700px;margin:32px auto;background:#fff;border-radius:12px;overflow:hidden;box-shadow:0 2px 16px rgba(0,0,0,.08);">
  <div style="background:linear-gradient(135deg,#667eea 0%,#764ba2 100%);padding:32px 40px;">
    <h1 style="margin:0;color:#fff;font-size:22px;font-weight:700;">Gmail Intelligence - Bao Cao Hang Ngay</h1>
    <p style="margin:8px 0 0;color:rgba(255,255,255,.8);font-size:14px;">{date_label}</p>
  </div>
  <div style="display:flex;border-bottom:1px solid #e2e8f0;">
    <div style="flex:1;padding:20px;border-right:1px solid #e2e8f0;text-align:center;">
      <div style="font-size:28px;font-weight:700;color:#e53e3e;">{len(urgent)}</div>
      <div style="font-size:12px;color:#718096;">URGENT</div>
    </div>
    <div style="flex:1;padding:20px;border-right:1px solid #e2e8f0;text-align:center;">
      <div style="font-size:28px;font-weight:700;color:#dd6b20;">{len(important)}</div>
      <div style="font-size:12px;color:#718096;">IMPORTANT</div>
    </div>
    <div style="flex:1;padding:20px;text-align:center;">
      <div style="font-size:28px;font-weight:700;color:#3182ce;">{len(emails)}</div>
      <div style="font-size:12px;color:#718096;">Tong cong</div>
    </div>
  </div>
  <div style="padding:24px 28px;">
    <h2 style="margin:0 0 16px;font-size:16px;color:#2d3748;">Danh sach email can chu y hom nay</h2>
    <table style="width:100%;border-collapse:collapse;font-size:13px;">
      <thead>
        <tr style="background:#f7fafc;">
          <th style="padding:8px;text-align:left;color:#718096;font-size:11px;">UU TIEN</th>
          <th style="padding:8px;text-align:left;color:#718096;font-size:11px;">EMAIL</th>
          <th style="padding:8px;text-align:left;color:#718096;font-size:11px;">DANH MUC</th>
          <th style="padding:8px;text-align:left;color:#718096;font-size:11px;">HANH DONG</th>
          <th style="padding:8px;text-align:left;color:#718096;font-size:11px;">NGAY NHAN</th>
        </tr>
      </thead>
      <tbody>{rows_html}</tbody>
    </table>
  </div>
  <div style="background:#f7fafc;padding:16px 28px;border-top:1px solid #e2e8f0;text-align:center;">
    <p style="margin:0;color:#a0aec0;font-size:11px;">
      Gui tu dong boi Gmail Intelligence Dashboard luc {now_str} -
      <a href="http://localhost:8000" style="color:#667eea;">Mo Dashboard</a>
    </p>
  </div>
</div>
</body></html>"""


def _get_gmail_owner(service) -> str:
    profile = service.users().getProfile(userId='me').execute()
    return profile.get('emailAddress', '')


def _create_raw_message(to_email: str, subject: str, html_body: str) -> str:
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = to_email
    msg["To"] = to_email
    msg.attach(MIMEText(html_body, "html", "utf-8"))
    return base64.urlsafe_b64encode(msg.as_bytes()).decode()


def send_daily_digest(db: Session, date: Optional[datetime.date] = None) -> dict:
    """Generate and send the daily digest email via Gmail API."""
    if date is None:
        date = datetime.date.today()

    today_start = datetime.datetime(date.year, date.month, date.day, 0, 0, 0)
    today_end = datetime.datetime(date.year, date.month, date.day, 23, 59, 59)

    from sqlalchemy.orm import joinedload

    emails: List[EmailModel] = (
        db.query(EmailModel)
        .join(ClassificationModel)
        .filter(
            ClassificationModel.priority.in_(["URGENT", "IMPORTANT"]),
            EmailModel.date_received >= today_start,
            EmailModel.date_received <= today_end,
        )
        .options(joinedload(EmailModel.classification), joinedload(EmailModel.actions))
        .order_by(ClassificationModel.importance_score.desc())
        .all()
    )

    creds = get_saved_credentials()
    if not creds or not creds.valid:
        raise PermissionError("Gmail OAuth credentials not valid. Please login via /login.")

    service = build("gmail", "v1", credentials=creds)
    recipient = settings.NOTIFY_EMAIL or _get_gmail_owner(service)

    html_body = build_digest_html(emails, date)
    subject = f"Gmail Intelligence - Bao Cao Hang Ngay {date.strftime('%d/%m/%Y')} - {len(emails)} email quan trong"
    raw = _create_raw_message(to_email=recipient, subject=subject, html_body=html_body)

    service.users().messages().send(userId="me", body={"raw": raw}).execute()
    logger.info(f"[DailyDigest] Sent to {recipient} - {len(emails)} important emails for {date}")

    return {"status": "sent", "recipient": recipient, "email_count": len(emails), "date": str(date)}


def get_digest_preview(db: Session, date: Optional[datetime.date] = None) -> dict:
    """Return HTML preview + metadata without sending."""
    if date is None:
        date = datetime.date.today()

    today_start = datetime.datetime(date.year, date.month, date.day, 0, 0, 0)
    today_end = datetime.datetime(date.year, date.month, date.day, 23, 59, 59)

    from sqlalchemy.orm import joinedload

    emails: List[EmailModel] = (
        db.query(EmailModel)
        .join(ClassificationModel)
        .filter(
            ClassificationModel.priority.in_(["URGENT", "IMPORTANT"]),
            EmailModel.date_received >= today_start,
            EmailModel.date_received <= today_end,
        )
        .options(joinedload(EmailModel.classification), joinedload(EmailModel.actions))
        .order_by(ClassificationModel.importance_score.desc())
        .all()
    )

    html = build_digest_html(emails, date)
    return {
        "date": str(date),
        "email_count": len(emails),
        "urgent_count": sum(1 for e in emails if e.classification and e.classification.priority == "URGENT"),
        "important_count": sum(1 for e in emails if e.classification and e.classification.priority == "IMPORTANT"),
        "html": html,
        "emails": [
            {
                "id": e.id,
                "subject": e.subject,
                "sender": e.sender_email,
                "priority": e.classification.priority if e.classification else None,
                "category": e.classification.category if e.classification else None,
                "action": e.classification.action_status if e.classification else None,
                "date_received": e.date_received.isoformat() if e.date_received else None,
            }
            for e in emails
        ],
    }
