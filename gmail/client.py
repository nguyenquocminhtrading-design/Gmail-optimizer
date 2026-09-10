from googleapiclient.discovery import build
from gmail.auth import get_saved_credentials
from gmail.fetch import fetch_recent_message_ids, fetch_email_details
from gmail.labels import LabelManager
from typing import Optional, List, Dict, Any

class GmailClient:
    def __init__(self):
        creds = get_saved_credentials()
        if not creds or not creds.valid:
            raise PermissionError("Gmail OAuth credentials not valid or missing. Please login via /login.")
        self.service = build('gmail', 'v1', credentials=creds)
        self.label_manager = LabelManager(self.service)

    def init_labels(self):
        return self.label_manager.sync_labels()

    def get_messages(self, max_results: int = 50, query: str = "") -> List[Dict[str, Any]]:
        message_ids = fetch_recent_message_ids(self.service, max_results=max_results, query=query)
        emails = []
        for msg_id in message_ids:
            try:
                details = fetch_email_details(self.service, msg_id)
                emails.append(details)
            except Exception as e:
                print(f"Error fetching message {msg_id}: {e}")
        return emails

    def apply_labels(self, message_id: str, label_names: List[str], dry_run: bool = True):
        self.label_manager.apply_labels_to_message(message_id, label_names, dry_run=dry_run)

    def archive(self, message_id: str, dry_run: bool = True):
        self.label_manager.archive_message(message_id, dry_run=dry_run)
