from typing import Any, Dict, List

from sqlalchemy.orm import Session

from classification.classifier import process_and_classify_email
from config import settings
from gmail.auth import is_authenticated
from gmail.client import GmailClient
from gmail.telegram_notifier import notify_important_email


def run_inbox_sync(db: Session, max_results: int = 30) -> Dict[str, Any]:
    if not is_authenticated():
        raise PermissionError("Gmail not authenticated")

    client = GmailClient()
    client.init_labels()
    emails_fetched = client.get_messages(max_results=max_results)

    processed_results: List[Dict[str, Any]] = []
    for raw_email in emails_fetched:
        res = process_and_classify_email(db, raw_email)
        processed_results.append(res)
        
        # Send Telegram alert if newly processed and important/urgent
        if res.get("status") == "classified":
            priority = (res.get("priority") or "").upper()
            if priority in ["IMPORTANT", "URGENT"]:
                notify_important_email(
                    sender=raw_email.get("sender_name") or raw_email.get("sender_email") or "Unknown",
                    subject=raw_email.get("subject") or "(No Subject)",
                    priority=priority,
                    category=(res.get("category") or "").upper(),
                )

        if (
            not settings.DRY_RUN
            and settings.AUTO_LABEL
            and res.get("target_labels")
            and res.get("status") != "already_processed"
        ):
            client.apply_labels(raw_email["gmail_message_id"], res["target_labels"], dry_run=False)

    return {
        "status": "success",
        "processed_count": len(processed_results),
        "details": processed_results,
        "dry_run": settings.DRY_RUN,
    }
