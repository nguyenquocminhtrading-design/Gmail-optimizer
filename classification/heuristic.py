import re
from typing import Dict, Any, List

# Keyword maps
CATEGORY_KEYWORDS = {
    "CAREER": ["interview", "job application", "recruiter", "internship", "career", "hiring manager", "offer letter", "resume"],
    "UNIVERSITY": ["professor", "thesis", "assignment", "university", "syllabus", "grade", "exam", "course", "lecture", "student"],
    "FINANCE": ["statement", "invoice", "payment due", "bank", "receipt", "credit card", "billing", "tax", "payroll", "dividend"],
    "WORK": ["sprint", "meeting notes", "jira", "github", "standup", "deploy", "project update", "client", "quarterly"],
    "PROMOTION": ["% off", "discount", "sale", "special offer", "clearance", "exclusive deal", "buy now", "limited time", "free shipping"],
    "NEWSLETTER": ["digest", "newsletter", "weekly round-up", "unsubscribing", "view in browser", "edition"],
    "NOTIFICATION": ["security alert", "password reset", "verification code", "two-factor", "login attempt"]
}

URGENCY_KEYWORDS = [
    "urgent", "as soon as possible", "asp", "immediately", "deadline", "due today",
    "due tomorrow", "final notice", "action required", "expires", "starting soon"
]

def classify_heuristically(
    subject: str,
    normalized_body: str,
    sender_email: str,
    has_deadlines: bool,
    action_status: str,
    has_attachments: bool,
    sender_stats: Dict[str, Any]
) -> Dict[str, Any]:
    text = f"{subject} {normalized_body}".lower()
    reasons = []
    
    # 1. Category Detection
    category = "OTHER"
    max_cat_score = 0
    for cat, keywords in CATEGORY_KEYWORDS.items():
        score = sum(1 for kw in keywords if kw in text)
        if score > max_cat_score:
            max_cat_score = score
            category = cat

    if max_cat_score > 0:
        reasons.append(f"Matched {max_cat_score} category keyword(s) for {category}")

    # 2. Urgency Detection
    urgency_hits = [kw for kw in URGENCY_KEYWORDS if kw in text]
    is_urgent = len(urgency_hits) > 0 or has_deadlines

    if urgency_hits:
        reasons.append(f"Contains urgency keywords: {', '.join(urgency_hits[:3])}")
    if has_deadlines:
        reasons.append("Email contains explicit upcoming deadline")

    # 3. Importance Score Calculation (0 to 100)
    score = 40.0 # Base score

    # Sender signal
    if sender_stats.get("avg_importance", 50.0) > 70.0:
        score += 20.0
        reasons.append(f"Sender {sender_email} historically high importance")
    elif sender_stats.get("avg_importance", 50.0) < 30.0:
        score -= 15.0

    # Category signal
    if category in ["CAREER", "UNIVERSITY", "WORK", "FINANCE"]:
        score += 15.0
    elif category in ["PROMOTION", "NEWSLETTER"]:
        score -= 30.0
        reasons.append(f"Category is promotional/newsletter")

    # Action required signal
    if action_status == "ACTION_REQUIRED":
        score += 20.0
        reasons.append("Requires recipient action")

    # Deadline signal
    if has_deadlines:
        score += 15.0

    # Attachment relevance
    if has_attachments and category in ["FINANCE", "WORK", "CAREER"]:
        score += 10.0
        reasons.append("Contains relevant document/attachment")

    # Clamp score 0 to 100
    score = max(0.0, min(100.0, score))

    # Priority Decision
    if is_urgent and score >= 70.0:
        priority = "URGENT"
    elif score >= 65.0:
        priority = "IMPORTANT"
    elif score <= 35.0:
        priority = "LOW_PRIORITY"
    else:
        priority = "NORMAL"

    # Confidence calculation heuristic
    confidence = 0.75
    if category in ["PROMOTION", "NEWSLETTER"] and priority == "LOW_PRIORITY":
        confidence = 0.92
    elif priority in ["URGENT", "IMPORTANT"] and has_deadlines and action_status == "ACTION_REQUIRED":
        confidence = 0.94
    elif max_cat_score == 0:
        confidence = 0.65

    return {
        "priority": priority,
        "category": category,
        "importance_score": score,
        "confidence": confidence,
        "reasons": reasons
    }
