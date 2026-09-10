from sqlalchemy.orm import Session
from database.models import RuleModel
from typing import Optional, Dict, Any

def evaluate_rules(db: Session, sender_email: str, subject: str, body: str) -> Optional[Dict[str, Any]]:
    rules = db.query(RuleModel).all()
    sender_lower = sender_email.lower()
    subject_lower = subject.lower()
    body_lower = body.lower()

    for rule in rules:
        cond_val = rule.condition_value.lower()
        matched = False
        
        if rule.condition_type == "SENDER" and cond_val in sender_lower:
            matched = True
        elif rule.condition_type == "SUBJECT_CONTAINS" and cond_val in subject_lower:
            matched = True
        elif rule.condition_type == "KEYWORD" and (cond_val in subject_lower or cond_val in body_lower):
            matched = True

        if matched:
            return {
                "priority": rule.target_priority,
                "category": rule.target_category,
                "action_status": rule.target_action,
                "never_archive": rule.never_archive,
                "confidence": 1.0,
                "matched_rule_id": rule.id,
                "reason": f"Matched user rule: {rule.condition_type} = '{rule.condition_value}'"
            }

    return None
