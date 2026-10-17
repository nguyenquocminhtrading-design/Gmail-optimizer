import urllib.request
import urllib.parse
import json
import sys
import os
from typing import Optional

# Ensure project root is on sys.path so 'config' can be found
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import settings

def send_telegram_message(message: str) -> bool:
    """Send text message to configured Telegram Chat ID."""
    token = settings.TELEGRAM_BOT_TOKEN
    chat_id = settings.TELEGRAM_CHAT_ID
    if not token or not chat_id:
        return False

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": message,
        "parse_mode": "HTML"
    }
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})

    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            return resp.status == 200
    except Exception as e:
        print(f"Telegram notification error: {e}")
        return False


def notify_important_email(sender: str, subject: str, priority: str, category: str, summary: str = "") -> bool:
    """Format and send Telegram alert for important/urgent emails."""
    icon = "🚨" if priority.upper() == "URGENT" else "⭐"
    msg = (
        f"{icon} <b>GMAIL OPTIMIZER ALERT</b> {icon}\n\n"
        f"<b>From:</b> {sender}\n"
        f"<b>Subject:</b> {subject}\n"
        f"<b>Priority:</b> {priority.upper()}\n"
        f"<b>Category:</b> {category.upper()}\n"
    )
    if summary:
        msg += f"\n<b>Summary:</b> {summary}\n"

    return send_telegram_message(msg)


def _verify_bot_token(token: str) -> Optional[str]:
    """Call getMe to verify the bot token. Returns bot username or None on failure."""
    try:
        url = f"https://api.telegram.org/bot{token}/getMe"
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            if data.get("ok"):
                return data["result"].get("username", "unknown")
    except Exception as e:
        print(f"[Telegram] ❌ Failed to verify bot token: {e}")
    return None


def start_telegram_bot_listener():
    """Start background polling thread to listen for user messages on Telegram."""
    import threading
    import time
    from database.db import SessionLocal
    from classification.coworker import handle_chat

    token = settings.TELEGRAM_BOT_TOKEN
    chat_id = settings.TELEGRAM_CHAT_ID

    if not token or not chat_id:
        print("[Telegram] ⚠️  TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID not set — bot listener not started.")
        return

    # --- Startup validation ---
    bot_username = _verify_bot_token(token)
    if not bot_username:
        print("[Telegram] ❌ Bot token invalid or network error — listener not started.")
        return

    print(f"[Telegram] ✅ Bot verified: @{bot_username} | Authorized chat_id: {chat_id}")
    print(f"[Telegram] 💡 If bot is not responding, make sure you have sent /start to @{bot_username} first.")

    def _poll_loop():
        offset = None
        print("[Telegram] 🤖 Polling listener started — waiting for messages...")
        while True:
            try:
                url = f"https://api.telegram.org/bot{token}/getUpdates?timeout=30"
                if offset:
                    url += f"&offset={offset}"
                req = urllib.request.Request(url)
                with urllib.request.urlopen(req, timeout=35) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                    if data.get("ok"):
                        for update in data.get("result", []):
                            offset = update["update_id"] + 1
                            msg = update.get("message", {})
                            text = msg.get("text", "").strip()
                            from_id = str(msg.get("chat", {}).get("id", ""))
                            from_name = msg.get("chat", {}).get("first_name", "unknown")

                            if not text:
                                continue

                            # Security: only respond to the authorized chat_id
                            if chat_id and from_id != str(chat_id):
                                print(f"[Telegram] ⛔ Ignored message from unauthorized chat_id={from_id} (@{from_name})")
                                continue

                            print(f"[Telegram] 📩 Message from {from_name} (id={from_id}): {text!r}")
                            db = SessionLocal()
                            try:
                                res = handle_chat(db, message=text, session_id=f"telegram-{from_id}")
                                reply_text = res.get("reply", "Done.")
                                sent = send_telegram_message(reply_text)
                                if sent:
                                    print(f"[Telegram] ✉️  Reply sent ({len(reply_text)} chars)")
                                else:
                                    print(f"[Telegram] ❌ Failed to send reply")
                            except Exception as chat_err:
                                print(f"[Telegram] ❌ Chat handler error: {chat_err}")
                                send_telegram_message(f"⚠️ Internal error: {str(chat_err)[:200]}")
                            finally:
                                db.close()

            except Exception as e:
                print(f"[Telegram] ⚠️  Poll error (retrying in 5s): {e}")
                time.sleep(5)

    thread = threading.Thread(target=_poll_loop, daemon=True)
    thread.start()
