import sys
import datetime
from database.db import SessionLocal, init_db
from gmail.auth import is_authenticated
from gmail.client import GmailClient
from classification.classifier import process_and_classify_email
from config import settings

def run_sync():
    print(f"[{datetime.datetime.now().isoformat()}] Starting Gmail Background Sync...")
    init_db()
    
    if not is_authenticated():
        print("ERROR: Gmail OAuth tokens missing or expired. Please authenticate via the Web Dashboard.")
        sys.exit(1)

    db = SessionLocal()
    try:
        client = GmailClient()
        print("Syncing Gmail namespace AI/ labels...")
        client.init_labels()
        
        print("Fetching recent messages from Gmail...")
        raw_emails = client.get_messages(max_results=50)
        print(f"Fetched {len(raw_emails)} emails. Processing classification pipeline...")

        auto_classified = 0
        needs_review = 0

        for raw_email in raw_emails:
            res = process_and_classify_email(db, raw_email)
            if res.get('status') == 'already_processed':
                continue

            if res.get('status') == 'AUTO_CLASSIFIED':
                auto_classified += 1
            else:
                needs_review += 1

            if not settings.DRY_RUN and res.get('target_labels'):
                client.apply_labels(raw_email['gmail_message_id'], res['target_labels'], dry_run=False)

        print(f"[{datetime.datetime.now().isoformat()}] Sync Finished. Auto-classified: {auto_classified}, Needs Review: {needs_review}")
    except Exception as e:
        print(f"ERROR during sync execution: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    run_sync()
