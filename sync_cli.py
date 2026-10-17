import sys
import datetime
from database.db import SessionLocal, init_db
from gmail.auth import is_authenticated
from gmail.sync_service import run_inbox_sync


def run_sync():
    print(f"[{datetime.datetime.now().isoformat()}] Starting Gmail Background Sync...")
    init_db()

    if not is_authenticated():
        print("ERROR: Gmail OAuth tokens missing or expired. Please authenticate via the Web Dashboard.")
        sys.exit(1)

    db = SessionLocal()
    try:
        result = run_inbox_sync(db, max_results=50)
        auto_classified = sum(1 for d in result.get("details", []) if d.get("status") == "AUTO_CLASSIFIED")
        needs_review = sum(1 for d in result.get("details", []) if d.get("status") == "NEEDS_REVIEW")
        print(
            f"[{datetime.datetime.now().isoformat()}] Sync Finished. "
            f"Processed: {result.get('processed_count', 0)}, "
            f"Auto-classified: {auto_classified}, Needs Review: {needs_review}, "
            f"DRY_RUN={result.get('dry_run')}"
        )
    except Exception as e:
        print(f"ERROR during sync execution: {e}")
    finally:
        db.close()


if __name__ == "__main__":
    run_sync()
