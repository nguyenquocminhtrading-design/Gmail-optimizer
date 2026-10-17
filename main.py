import os
from contextlib import asynccontextmanager
from typing import List, Optional

from fastapi import FastAPI, Request, Depends, HTTPException, UploadFile, File
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from sqlalchemy.orm import Session

from classification.coworker import handle_chat
from classification.label_map import target_labels_for
from classification.llm_providers import llm_status
from classification.speech_providers import transcribe_audio, speak_text
from config import settings
from database.db import get_db, init_db
from database.repository import EmailRepository
from gmail.auth import is_authenticated, get_authorization_url, exchange_code_for_token
from gmail.client import GmailClient
from gmail.sync_service import run_inbox_sync
from gmail.telegram_notifier import start_telegram_bot_listener

init_db()


@asynccontextmanager
async def lifespan(app: FastAPI):
    start_telegram_bot_listener()
    yield


app = FastAPI(title="Gmail Intelligence & Email Classification System", lifespan=lifespan)

app.mount("/static", StaticFiles(directory="dashboard/static"), name="static")
templates = Jinja2Templates(directory="dashboard/templates")


class FeedbackRequest(BaseModel):
    email_id: int
    new_priority: str
    new_category: str
    new_action: str
    scope: str = "THIS_EMAIL"
    reason: Optional[str] = None


class ChatRequest(BaseModel):
    message: str = ""
    session_id: Optional[str] = None
    confirm: bool = False
    email_ids: Optional[List[int]] = None


def _apply_gmail_labels_for_email(email) -> dict:
    if not email or not email.classification:
        return {"wrote": False, "labels": []}
    labels = target_labels_for(
        email.classification.priority,
        email.classification.category,
        email.classification.action_status,
        email.classification.status,
    )
    wrote = False
    if not settings.DRY_RUN and is_authenticated() and labels:
        client = GmailClient()
        client.init_labels()
        client.apply_labels(email.gmail_message_id, labels, dry_run=False)
        wrote = True
    return {"wrote": wrote, "labels": labels, "dry_run": settings.DRY_RUN}


@app.get("/", response_class=HTMLResponse)
def index_page(request: Request):
    if not is_authenticated():
        return templates.TemplateResponse(request=request, name="login.html")

    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={
            "is_dry_run": settings.DRY_RUN,
            "confidence_threshold": settings.CONFIDENCE_AUTO_CLASSIFY,
            "llm": llm_status(),
        },
    )


@app.get("/login")
def login_route():
    try:
        auth_url, state = get_authorization_url()
        return RedirectResponse(auth_url)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"OAuth login failed: {str(e)}")


@app.get("/oauth2callback")
def oauth_callback(code: str, state: Optional[str] = None):
    try:
        exchange_code_for_token(code=code, state=state)
        return RedirectResponse(url="/")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Authentication callback error: {str(e)}")


@app.get("/logout")
def logout_route():
    if os.path.exists(settings.TOKEN_FILE_PATH):
        os.remove(settings.TOKEN_FILE_PATH)
    return RedirectResponse(url="/")


@app.get("/api/stats")
def get_stats(db: Session = Depends(get_db)):
    return EmailRepository.get_dashboard_stats(db)


@app.get("/api/review")
def get_review_queue(db: Session = Depends(get_db)):
    emails = EmailRepository.get_review_queue(db)
    result = []
    for e in emails:
        result.append({
            "id": e.id,
            "gmail_message_id": e.gmail_message_id,
            "sender_name": e.sender_name,
            "sender_email": e.sender_email,
            "subject": e.subject,
            "date_received": e.date_received.isoformat(),
            "normalized_body": e.normalized_body,
            "classification": {
                "priority": e.classification.priority if e.classification else "NORMAL",
                "category": e.classification.category if e.classification else "OTHER",
                "action_status": e.classification.action_status if e.classification else "NO_ACTION",
                "confidence": e.classification.confidence if e.classification else 0.5,
                "reasons_json": e.classification.reasons_json if e.classification else "[]",
            },
        })
    return result


@app.get("/api/important")
def get_today_important(db: Session = Depends(get_db)):
    emails = EmailRepository.get_today_important_emails(db)
    result = []
    for e in emails:
        result.append({
            "id": e.id,
            "sender_name": e.sender_name,
            "sender_email": e.sender_email,
            "subject": e.subject,
            "date_received": e.date_received.isoformat(),
            "classification": {
                "priority": e.classification.priority if e.classification else "IMPORTANT",
                "category": e.classification.category if e.classification else "WORK",
            },
        })
    return result


@app.post("/api/feedback")
def submit_user_feedback(req: FeedbackRequest, db: Session = Depends(get_db)):
    try:
        feedback = EmailRepository.record_user_feedback(
            db=db,
            email_id=req.email_id,
            new_priority=req.new_priority,
            new_category=req.new_category,
            new_action=req.new_action,
            scope=req.scope,
            reason=req.reason,
        )
        email = EmailRepository.get_email_by_id(db, req.email_id)
        label_result = _apply_gmail_labels_for_email(email)
        return {
            "status": "success",
            "feedback_id": feedback.id,
            "labels": label_result.get("labels", []),
            "wrote_gmail": label_result.get("wrote", False),
            "dry_run": settings.DRY_RUN,
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/sync")
def trigger_sync(db: Session = Depends(get_db)):
    if not is_authenticated():
        raise HTTPException(status_code=401, detail="Gmail not authenticated")
    try:
        return run_inbox_sync(db, max_results=30)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Sync error: {str(e)}")


@app.get("/api/llm")
def get_llm_status():
    return llm_status()


@app.post("/api/chat")
def chat_with_coworker(req: ChatRequest, db: Session = Depends(get_db)):
    try:
        return handle_chat(
            db,
            message=req.message or "briefing",
            session_id=req.session_id,
            confirm=req.confirm,
            email_ids=req.email_ids,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/mode")
def set_run_mode(data: dict):
    mode = data.get("mode")
    if mode not in ["dry_run", "live"]:
        raise HTTPException(status_code=400, detail="Invalid mode")
    
    is_dry = (mode == "dry_run")
    settings.DRY_RUN = is_dry
    
    env_path = ".env"
    if os.path.exists(env_path):
        try:
            with open(env_path, "r", encoding="utf-8") as f:
                lines = f.readlines()
            new_lines = []
            found = False
            for line in lines:
                if line.startswith("DRY_RUN="):
                    new_lines.append(f"DRY_RUN={'True' if is_dry else 'False'}\n")
                    found = True
                else:
                    new_lines.append(line)
            if not found:
                new_lines.append(f"DRY_RUN={'True' if is_dry else 'False'}\n")
            with open(env_path, "w", encoding="utf-8") as f:
                f.writelines(new_lines)
        except Exception as e:
            print("Failed to rewrite .env file:", e)
            
    return {"status": "success", "dry_run": settings.DRY_RUN}


# ---------------------------------------------------------------------------
# Speech endpoints (Groq Whisper STT + Groq Orpheus TTS)
# Enabled via .env: GROQ_STT_ENABLED=True / GROQ_TTS_ENABLED=True
# ---------------------------------------------------------------------------

@app.post("/api/transcribe")
async def api_transcribe(file: UploadFile = File(...)):
    """Upload an audio file and get back the transcribed text (Groq Whisper)."""
    if not settings.GROQ_STT_ENABLED:
        raise HTTPException(
            status_code=503,
            detail="Speech-to-Text is disabled. Set GROQ_STT_ENABLED=True in .env to enable.",
        )
    audio_bytes = await file.read()
    text = transcribe_audio(audio_bytes, filename=file.filename or "audio.wav")
    if text is None:
        raise HTTPException(status_code=502, detail="Transcription failed — check server logs.")
    return {"transcript": text, "model": settings.GROQ_STT_MODEL}


class SpeakRequest(BaseModel):
    text: str
    voice: Optional[str] = None


@app.post("/api/speak")
def api_speak(req: SpeakRequest):
    """Convert text to speech using Groq Orpheus TTS. Returns mp3 audio."""
    if not settings.GROQ_TTS_ENABLED:
        raise HTTPException(
            status_code=503,
            detail="Text-to-Speech is disabled. Set GROQ_TTS_ENABLED=True in .env to enable.",
        )
    if not req.text.strip():
        raise HTTPException(status_code=400, detail="'text' must not be empty.")
    audio = speak_text(req.text, voice=req.voice)
    if audio is None:
        raise HTTPException(status_code=502, detail="TTS synthesis failed — check server logs.")
    return Response(content=audio, media_type="audio/mpeg")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=settings.PORT, reload=True)
