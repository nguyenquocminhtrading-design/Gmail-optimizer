import re
import datetime
from dateutil import parser as date_parser
from typing import List, Dict, Any, Optional

WEEKDAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]

def extract_deadlines_heuristic(text: str, email_date: datetime.datetime) -> List[Dict[str, Any]]:
    deadlines = []
    if not text:
        return deadlines

    lower_text = text.lower()
    
    # 1. "due today", "due tomorrow", "due by tomorrow"
    if "today" in lower_text and re.search(r'\b(due|submit|deadline|by|before)\b.*today', lower_text):
        deadlines.append({
            "title": "Action due today",
            "deadline_date": email_date.replace(hour=23, minute=59, second=59),
            "is_relative": True,
            "confidence": 0.90
        })
    elif "tomorrow" in lower_text and re.search(r'\b(due|submit|deadline|by|before)\b.*tomorrow', lower_text):
        target_date = email_date + datetime.timedelta(days=1)
        deadlines.append({
            "title": "Action due tomorrow",
            "deadline_date": target_date.replace(hour=23, minute=59, second=59),
            "is_relative": True,
            "confidence": 0.90
        })

    # 2. Weekday extraction (e.g., "by Friday", "due on Monday")
    for idx, day in enumerate(WEEKDAYS):
        match = re.search(rf'\b(by|before|on|due)\s+{day}\b', lower_text)
        if match:
            days_ahead = (idx - email_date.weekday() + 7) % 7
            if days_ahead == 0:
                days_ahead = 7
            target_date = email_date + datetime.timedelta(days=days_ahead)
            deadlines.append({
                "title": f"Action due by {day.capitalize()}",
                "deadline_date": target_date.replace(hour=23, minute=59, second=59),
                "is_relative": True,
                "confidence": 0.85
            })

    # 3. Explicit date patterns (e.g. "September 15", "15 Sept", "30/09/2026", "2026-09-15")
    date_patterns = [
        r'\b(?:deadline|due|submit by|expires|due date)[:\s]+([A-Za-z]+\s+\d{1,2}(?:st|nd|rd|th)?(?:\s*,\s*\d{4})?)',
        r'\b(?:deadline|due|submit by|expires|due date)[:\s]+(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})',
        r'\b([A-Z][a-z]+\s+\d{1,2}(?:st|nd|rd|th)?\s+at\s+\d{1,2}(?::\d{2})?\s*(?:AM|PM|am|pm)?)'
    ]

    for pattern in date_patterns:
        matches = re.finditer(pattern, text, re.IGNORECASE)
        for m in matches:
            date_str = m.group(1)
            try:
                dt = date_parser.parse(date_str, fuzzy=True, default=email_date)
                if dt < email_date - datetime.timedelta(days=1):
                    # If parsed date is in the past, adjust year if year wasn't explicit
                    dt = dt.replace(year=email_date.year + 1)
                deadlines.append({
                    "title": f"Deadline: {m.group(0)[:60]}",
                    "deadline_date": dt,
                    "is_relative": False,
                    "confidence": 0.92
                })
            except Exception:
                pass

    return deadlines
