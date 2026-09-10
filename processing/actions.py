import re
from typing import List, Dict, Any

ACTION_PATTERNS = [
    (r'\b(please sign|sign the attached|signature required)\b', "Sign document"),
    (r'\b(confirm your attendance|rsvps?|please confirm|schedule an interview)\b', "Confirm attendance / schedule"),
    (r'\b(payment due|please pay|invoice due|complete payment)\b', "Pay bill / invoice"),
    (r'\b(please submit|submit your|upload your)\b', "Submit required material/document"),
    (r'\b(please reply|waiting for your response|let me know if)\b', "Reply to email"),
    (r'\b(fill out|complete the survey|feedback requested)\b', "Complete form/survey")
]

def detect_action_items(text: str, subject: str = "") -> tuple[str, List[str]]:
    combined = f"{subject} {text}".lower()
    actions = []

    for pattern, action_desc in ACTION_PATTERNS:
        if re.search(pattern, combined):
            actions.append(action_desc)

    if actions:
        action_status = "ACTION_REQUIRED"
    elif re.search(r'\b(waiting for reply|awaiting response)\b', combined):
        action_status = "WAITING_FOR_REPLY"
        actions.append("Waiting for external response")
    else:
        action_status = "NO_ACTION"

    return action_status, actions
