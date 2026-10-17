from __future__ import annotations

import json
import re
import uuid
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from classification.label_map import target_labels_for
from classification.llm_providers import gemini_configured, polish_coworker_reply
from config import settings
from database.models import EmailModel
from database.repository import EmailRepository
from gmail.auth import is_authenticated
from gmail.client import GmailClient
from gmail.sync_service import run_inbox_sync


CONFIRM_RE = re.compile(
    r"\b(yes|yep|ok|okay|apply|label|confirm|dong y|đồng ý|xac nhan|xác nhận|gan nhan|gắn nhãn|ok luôn)\b",
    re.IGNORECASE,
)
SYNC_RE = re.compile(r"\b(sync|dong bo|đồng bộ|fetch|keo mail|kéo mail)\b", re.IGNORECASE)
REVIEW_RE = re.compile(r"\b(review|can quyet dinh|cần quyết định|chua chac|chưa chắc)\b", re.IGNORECASE)
ACTION_RE = re.compile(r"\b(action|deadline|han|hạn|can lam|cần làm|viec can|việc cần)\b", re.IGNORECASE)
IMPORTANT_RE = re.compile(
    r"\b(important|urgent|quan trong|quan trọng|gap|gấp|brief|briefing|hom nay|hôm nay|inbox)\b",
    re.IGNORECASE,
)

PRIORITY_WORDS = {
    "URGENT": ["urgent", "gấp", "gap"],
    "IMPORTANT": ["important", "quan trọng", "quan trong"],
    "NORMAL": ["normal", "binh thuong", "bình thường"],
    "LOW_PRIORITY": ["low", "newsletter", "promo", "quang cao", "quảng cáo"],
}
CATEGORY_WORDS = {
    "CAREER": ["career", "job", "internship", "viec lam", "việc làm", "thuc tap", "thực tập"],
    "UNIVERSITY": ["university", "school", "dai hoc", "đại học", "truong"],
    "FINANCE": ["finance", "bank", "invoice", "tai chinh", "tài chính"],
    "WORK": ["work", "cong viec", "công việc", "jira", "github"],
    "PERSONAL": ["personal", "ca nhan", "cá nhân"],
    "NEWSLETTER": ["newsletter", "digest"],
    "PROMOTION": ["promotion", "sale", "deal"],
}


def email_to_card(email: EmailModel) -> Dict[str, Any]:
    cls = email.classification
    priority = cls.priority if cls else "NORMAL"
    category = cls.category if cls else "OTHER"
    action = cls.action_status if cls else "NO_ACTION"
    status = cls.status if cls else "NEEDS_REVIEW"
    confidence = cls.confidence if cls else 0.0
    reasons = []
    if cls and cls.reasons_json:
        try:
            reasons = json.loads(cls.reasons_json)
        except json.JSONDecodeError:
            reasons = []
    labels = target_labels_for(priority, category, action, status)
    preview = (email.normalized_body or "")[:240]
    return {
        "id": email.id,
        "gmail_message_id": email.gmail_message_id,
        "sender_name": email.sender_name,
        "sender_email": email.sender_email,
        "subject": email.subject,
        "date_received": email.date_received.isoformat() if email.date_received else None,
        "preview": preview,
        "priority": priority,
        "category": category,
        "action_status": action,
        "confidence": confidence,
        "status": status,
        "reasons": reasons,
        "proposed_labels": labels,
        "deadlines": [
            {
                "title": d.title,
                "deadline_date": d.deadline_date.isoformat() if d.deadline_date else None,
            }
            for d in (email.deadlines or [])
        ],
    }


def _apply_labels_to_emails(db: Session, email_ids: List[int]) -> Dict[str, Any]:
    applied = []
    skipped = []
    client = None
    if is_authenticated() and not settings.DRY_RUN:
        client = GmailClient()
        client.init_labels()

    for email_id in email_ids:
        email = EmailRepository.get_email_by_id(db, email_id)
        if not email or not email.classification:
            skipped.append(email_id)
            continue
        labels = target_labels_for(
            email.classification.priority,
            email.classification.category,
            email.classification.action_status,
            "USER_REVIEWED",
        )
        if client:
            client.apply_labels(email.gmail_message_id, labels, dry_run=False)
        applied.append({"id": email.id, "subject": email.subject, "labels": labels})

    return {
        "applied": applied,
        "skipped": skipped,
        "dry_run": settings.DRY_RUN,
        "wrote_gmail": bool(client),
    }


def _tool_get_briefing(db: Session) -> Dict[str, Any]:
    stats = EmailRepository.get_dashboard_stats(db)
    important = [email_to_card(e) for e in EmailRepository.get_today_important_emails(db, limit=10)]
    review = [email_to_card(e) for e in EmailRepository.get_review_queue(db, limit=8)]
    return {"stats": stats, "important": important, "needs_review": review}


def _tool_search(
    db: Session,
    query: Optional[str] = None,
    priority: Optional[str] = None,
    category: Optional[str] = None,
    action: Optional[str] = None,
    sender: Optional[str] = None,
    important_only: bool = False,
    needs_review: bool = False,
) -> Dict[str, Any]:
    emails = EmailRepository.search_emails(
        db,
        query=query,
        priority=priority,
        category=category,
        action=action,
        sender=sender,
        important_only=important_only,
        needs_review=needs_review,
        limit=15,
    )
    return {"emails": [email_to_card(e) for e in emails]}


def _infer_filters(message: str) -> Dict[str, Any]:
    filters: Dict[str, Any] = {}
    lower = message.lower()
    for pri, words in PRIORITY_WORDS.items():
        if any(w in lower for w in words):
            filters["priority"] = pri
            break
    for cat, words in CATEGORY_WORDS.items():
        if any(w in lower for w in words):
            filters["category"] = cat
            break
    if ACTION_RE.search(message):
        filters["action"] = "ACTION_REQUIRED"
    if REVIEW_RE.search(message):
        filters["needs_review"] = True
    sender_match = re.search(r"(?:from|tu|từ)\s+([^\s,]+@[^\s,]+)", message, re.IGNORECASE)
    if sender_match:
        filters["sender"] = sender_match.group(1)
    return filters


def _fallback_reply(db: Session, message: str, session_id: str, confirm: bool, email_ids: Optional[List[int]]) -> Dict[str, Any]:
    pending = email_ids or EmailRepository.get_pending_email_ids(db, session_id)
    wants_apply = confirm or bool(CONFIRM_RE.search(message))

    if wants_apply and pending:
        result = _apply_labels_to_emails(db, pending)
        EmailRepository.set_pending_email_ids(db, session_id, [])
        dry_note = (
            "DRY RUN đang bật — mình chỉ giả lập gắn nhãn, chưa ghi lên Gmail."
            if result["dry_run"]
            else "Đã ghi nhãn lên Gmail."
        )
        lines = [f"Đã xử lý {len(result['applied'])} email. {dry_note}"]
        for item in result["applied"][:10]:
            lines.append(f"- {item['subject']}: {', '.join(item['labels'])}")
        cards = []
        for item in result["applied"]:
            email = EmailRepository.get_email_by_id(db, item["id"])
            if email:
                cards.append(email_to_card(email))
        return {"text": "\n".join(lines), "cards": cards, "needs_confirm": False}

    if SYNC_RE.search(message):
        try:
            sync = run_inbox_sync(db, max_results=30)
            text = (
                f"Đã sync {sync['processed_count']} thư. "
                f"{'DRY RUN: chưa ghi nhãn Gmail.' if sync['dry_run'] else 'Nhãn auto đã được ghi (nếu đủ confidence).'}"
            )
            briefing = _tool_get_briefing(db)
            cards = briefing["important"] or briefing["needs_review"]
            EmailRepository.set_pending_email_ids(db, session_id, [c["id"] for c in cards])
            return {"text": text, "cards": cards, "needs_confirm": bool(cards)}
        except PermissionError:
            return {
                "text": "Chưa đăng nhập Gmail. Mở /login rồi sync lại.",
                "cards": [],
                "needs_confirm": False,
            }
        except Exception as exc:
            return {"text": f"Sync lỗi: {exc}", "cards": [], "needs_confirm": False}

    if REVIEW_RE.search(message):
        cards = [email_to_card(e) for e in EmailRepository.get_review_queue(db, limit=12)]
        EmailRepository.set_pending_email_ids(db, session_id, [c["id"] for c in cards])
        if not cards:
            return {"text": "Không còn thư nào cần bạn quyết định.", "cards": [], "needs_confirm": False}
        return {
            "text": f"Có {len(cards)} thư mình chưa chắc. Xem card rồi bấm Gắn nhãn hoặc sửa giúp mình.",
            "cards": cards,
            "needs_confirm": True,
        }

    filters = _infer_filters(message)
    looks_search = bool(filters) or len(message.strip()) > 12
    if looks_search and not IMPORTANT_RE.search(message) and not message.strip().endswith("?"):
        query = None
        if not filters.get("sender") and not filters.get("priority") and not filters.get("category"):
            query = message.strip()
        data = _tool_search(db, query=query, **{k: v for k, v in filters.items() if k != "needs_review"}, needs_review=filters.get("needs_review", False))
        cards = data["emails"]
        EmailRepository.set_pending_email_ids(db, session_id, [c["id"] for c in cards])
        if not cards:
            return {"text": "Không thấy email khớp. Thử sync trước, hoặc hỏi ‘thư quan trọng’.", "cards": [], "needs_confirm": False}
        return {
            "text": f"Tìm thấy {len(cards)} thư. Nếu đúng, nói ‘gắn nhãn’ hoặc bấm Gắn nhãn.",
            "cards": cards,
            "needs_confirm": True,
        }

    briefing = _tool_get_briefing(db)
    stats = briefing["stats"]
    cards = briefing["important"][:8] or briefing["needs_review"]
    EmailRepository.set_pending_email_ids(db, session_id, [c["id"] for c in cards])
    if stats["total_emails"] == 0:
        return {
            "text": "Inbox local đang trống. Bấm Sync Gmail (hoặc nhắn ‘sync’) rồi mình brief cho bạn.",
            "cards": [],
            "needs_confirm": False,
        }
    text = (
        f"Mình đã xem hộp thư local: {stats['urgent']} urgent, "
        f"{stats['important_today']} important, {stats['action_required']} cần hành động, "
        f"{stats['needs_review']} cần bạn quyết. "
        "Card bên dưới là những thư đáng chú ý. Nói ‘gắn nhãn’ nếu đồng ý."
    )
    return {"text": text, "cards": cards, "needs_confirm": bool(cards)}


def _gemini_reply(db: Session, message: str, session_id: str, history: List[Dict[str, str]]) -> Optional[Dict[str, Any]]:
    if not gemini_configured():
        return None
    try:
        from google import genai
        from google.genai import types
    except ImportError:
        return None

    declarations = [
        types.FunctionDeclaration(
            name="get_briefing",
            description="Brief urgent/important/action/review emails already stored locally.",
            parameters=types.Schema(type="OBJECT", properties={}),
        ),
        types.FunctionDeclaration(
            name="search_emails",
            description="Search stored emails by free text, sender, priority, category, or action.",
            parameters=types.Schema(
                type="OBJECT",
                properties={
                    "query": types.Schema(type="STRING"),
                    "sender": types.Schema(type="STRING"),
                    "priority": types.Schema(type="STRING"),
                    "category": types.Schema(type="STRING"),
                    "action": types.Schema(type="STRING"),
                    "important_only": types.Schema(type="BOOLEAN"),
                    "needs_review": types.Schema(type="BOOLEAN"),
                },
            ),
        ),
        types.FunctionDeclaration(
            name="sync_inbox",
            description="Fetch recent Gmail messages into the local database and classify them.",
            parameters=types.Schema(type="OBJECT", properties={}),
        ),
    ]

    contents = []
    for item in history[-8:]:
        contents.append(types.Content(role=item["role"], parts=[types.Part(text=item["text"])]))
    contents.append(types.Content(role="user", parts=[types.Part(text=message)]))

    client = genai.Client(api_key=settings.GEMINI_API_KEY)
    tool = types.Tool(function_declarations=declarations)
    config = types.GenerateContentConfig(
        system_instruction=(
            "You are a local inbox coworker. Speak Vietnamese unless the user writes in English. "
            "Use tools to inspect stored email. Never invent emails. "
            "Do not claim Gmail labels were written unless the user confirmed apply. "
            "If DRY_RUN would be on, remind them labels are simulated. "
            "Summarize like a teammate: what matters, why, what they should confirm."
        ),
        tools=[tool],
    )

    cards: List[Dict[str, Any]] = []
    last_function = None
    model_list = []
    if hasattr(settings, "GEMINI_MODELS") and settings.GEMINI_MODELS:
        model_list = [m.strip() for m in settings.GEMINI_MODELS.split(",") if m.strip()]
    else:
        model_list = [settings.GEMINI_MODEL]

    response = None
    for model in model_list:
        try:
            response = client.models.generate_content(
                model=model,
                contents=contents,
                config=config,
            )
            break  # success
        except Exception as exc:
            print(f"[Chat] Gemini/{model} failed: {exc}")
            response = None
            
    if not response:
        return None

    for _ in range(4):
        fn_call = None
        if response.function_calls:
            fn_call = response.function_calls[0]
        if not fn_call:
            break
        name = fn_call.name
        args = dict(fn_call.args or {})
        last_function = name
        if name == "get_briefing":
            payload = _tool_get_briefing(db)
            cards = payload["important"] or payload["needs_review"]
        elif name == "search_emails":
            payload = _tool_search(db, **args)
            cards = payload["emails"]
        elif name == "sync_inbox":
            try:
                payload = run_inbox_sync(db, max_results=30)
            except Exception as exc:
                payload = {"error": str(exc)}
            briefing = _tool_get_briefing(db)
            cards = briefing["important"] or briefing["needs_review"]
        else:
            payload = {"error": f"unknown tool {name}"}

        EmailRepository.set_pending_email_ids(db, session_id, [c["id"] for c in cards])
        contents.append(response.candidates[0].content)
        contents.append(
            types.Content(
                role="user",
                parts=[
                    types.Part.from_function_response(name=name, response=payload),
                ],
            )
        )
        response = None
        for model in model_list:
            try:
                response = client.models.generate_content(
                    model=model,
                    contents=contents,
                    config=config,
                )
                break
            except Exception as exc:
                print(f"[Chat tool loop] Gemini/{model} failed: {exc}")
                response = None
                
        if not response:
            return None

    text = (response.text or "").strip()
    if not text:
        return None
    EmailRepository.set_pending_email_ids(db, session_id, [c["id"] for c in cards])
    return {
        "text": text,
        "cards": cards,
        "needs_confirm": bool(cards) and last_function != "sync_inbox",
        "engine": "gemini",
    }


def handle_chat(
    db: Session,
    message: str,
    session_id: Optional[str] = None,
    confirm: bool = False,
    email_ids: Optional[List[int]] = None,
) -> Dict[str, Any]:
    session_id = session_id or str(uuid.uuid4())
    EmailRepository.get_or_create_chat_session(db, session_id)
    EmailRepository.add_chat_message(db, session_id, "user", message)

    pending = email_ids or EmailRepository.get_pending_email_ids(db, session_id)
    engine = "heuristic"
    if confirm or (CONFIRM_RE.search(message) and pending):
        result = _fallback_reply(db, message, session_id, confirm=True, email_ids=pending)
    else:
        history = []
        for msg in EmailRepository.get_chat_messages(db, session_id, limit=12):
            history.append({"role": "user" if msg.role == "user" else "model", "text": msg.content})
        result = _gemini_reply(db, message, session_id, history[:-1])
        if result is None:
            result = _fallback_reply(db, message, session_id, confirm=False, email_ids=email_ids)
            facts = {
                "dry_run": settings.DRY_RUN,
                "reply_draft": result["text"],
                "cards": [
                    {
                        "subject": c.get("subject"),
                        "sender": c.get("sender_email"),
                        "priority": c.get("priority"),
                        "category": c.get("category"),
                        "labels": c.get("proposed_labels"),
                    }
                    for c in (result.get("cards") or [])[:8]
                ],
            }
            polished = polish_coworker_reply(message, facts)
            if polished:
                result["text"] = polished
                engine = "qwen"
            else:
                engine = "heuristic"
        else:
            engine = result.get("engine") or "gemini"

    EmailRepository.add_chat_message(db, session_id, "assistant", result["text"], result.get("cards") or [])
    return {
        "session_id": session_id,
        "reply": result["text"],
        "cards": result.get("cards") or [],
        "needs_confirm": result.get("needs_confirm", False),
        "dry_run": settings.DRY_RUN,
        "engine": engine,
    }
