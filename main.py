import os
import json
from fastapi import FastAPI, Request, Depends, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional

from config import settings
from database.db import get_db, init_db
from database.repository import EmailRepository
from gmail.auth import is_authenticated, get_authorization_url, exchange_code_for_token
from gmail.client import GmailClient
from classification.classifier import process_and_classify_email

# Initialize DB
init_db()

app = FastAPI(title="Gmail Intelligence & Email Classification System")

# Mount Static Files & Templates
app.mount("/static", StaticFiles(directory="dashboard/static"), name="static")
templates = Jinja2Templates(directory="dashboard/templates")


class FeedbackRequest(BaseModel):
    email_id: int
    new_priority: str
    new_category: str
    new_action: str
    scope: str = "THIS_EMAIL"
    reason: Optional[str] = None


@app.get("/", response_class=HTMLResponse)
def index_page(request: Request):
    if not is_authenticated():
        return templates.TemplateResponse("login.html", {"request": request})
    
    return templates.TemplateResponse("index.html", {
        "request": request,
        "is_dry_run": settings.DRY_RUN,
        "confidence_threshold": settings.CONFIDENCE_AUTO_CLASSIFY
    })


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
                "reasons_json": e.classification.reasons_json if e.classification else "[]"
            }
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
                "category": e.classification.category if e.classification else "WORK"
            }
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
            reason=req.reason
        )
        return {"status": "success", "feedback_id": feedback.id}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/sync")
def trigger_sync(db: Session = Depends(get_db)):
    if not is_authenticated():
        raise HTTPException(status_code=401, detail="Gmail not authenticated")

    try:
        client = GmailClient()
        client.init_labels()
        emails_fetched = client.get_messages(max_results=30)
        
        processed_results = []
        for raw_email in emails_fetched:
            res = process_and_classify_email(db, raw_email)
            processed_results.append(res)
            
            # Apply labels if not dry run
            if not settings.DRY_RUN and res.get('target_labels'):
                client.apply_labels(raw_email['gmail_message_id'], res['target_labels'], dry_run=False)

        return {
            "status": "success",
            "processed_count": len(processed_results),
            "details": processed_results
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Sync error: {str(e)}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=settings.PORT, reload=True)
