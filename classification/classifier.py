import json
import datetime
from sqlalchemy.orm import Session
from config import settings
from database.repository import EmailRepository
from processing.normalize import normalize_email_body
from processing.deadlines import extract_deadlines_heuristic
from processing.actions import detect_action_items
from processing.attachments import classify_attachment
from classification.rules import evaluate_rules
from classification.heuristic import classify_heuristically
from classification.llm_engine import analyze_with_gemini
from classification.label_map import target_labels_for
from typing import Dict, Any

def process_and_classify_email(db: Session, email_data: dict) -> dict:
    # 1. Save or get email model
    existing = EmailRepository.get_by_gmail_id(db, email_data['gmail_message_id'])
    if existing:
        return {"status": "already_processed", "email_id": existing.id}

    # 2. Text Normalization
    normalized_body = normalize_email_body(
        email_data.get('body_plain', ''),
        email_data.get('body_html', '')
    )
    email_data['normalized_body'] = normalized_body
    
    email_obj = EmailRepository.create_email(db, email_data)

    # 3. Process Attachments
    for att in email_data.get('attachments', []):
        rel_cat = classify_attachment(att['filename'], att['mime_type'])
        EmailRepository.add_attachment(
            db, email_obj.id, att['filename'], att['mime_type'], att['size_bytes'], rel_cat
        )

    # 4. Extract Action & Deadlines
    action_status, action_items = detect_action_items(normalized_body, email_obj.subject)
    for act_desc in action_items:
        EmailRepository.add_action(db, email_obj.id, act_desc)

    deadlines = extract_deadlines_heuristic(normalized_body, email_obj.date_received)
    for dl in deadlines:
        EmailRepository.add_deadline(db, email_obj.id, dl['title'], dl['deadline_date'], dl['is_relative'], dl['confidence'])

    # 5. Evaluate Hard & Learned Rules
    rule_match = evaluate_rules(db, email_obj.sender_email, email_obj.subject, normalized_body)
    
    sender_stats = EmailRepository.get_sender_stats(db, email_obj.sender_email)

    if rule_match:
        final_priority = rule_match.get('target_priority') or "IMPORTANT"
        final_category = rule_match.get('target_category') or "WORK"
        final_action = rule_match.get('target_action') or action_status
        importance_score = 90.0 if final_priority in ["URGENT", "IMPORTANT"] else 20.0
        confidence = 1.0
        reasons = [rule_match['reason']]
    else:
        # Heuristic Classification
        heuristic_res = classify_heuristically(
            email_obj.subject,
            normalized_body,
            email_obj.sender_email,
            len(deadlines) > 0,
            action_status,
            email_obj.has_attachments,
            sender_stats
        )

        # Check optional Gemini API if enabled
        llm_res = analyze_with_gemini(email_obj.subject, email_obj.sender_email, normalized_body)

        if llm_res and llm_res.get('confidence', 0) > heuristic_res['confidence']:
            final_priority = llm_res.get('priority', heuristic_res['priority'])
            final_category = llm_res.get('category', heuristic_res['category'])
            final_action = llm_res.get('action_status', action_status)
            importance_score = float(llm_res.get('importance_score', heuristic_res['importance_score']))
            confidence = float(llm_res.get('confidence', heuristic_res['confidence']))
            reasons = llm_res.get('reasons', heuristic_res['reasons']) + ["Gemini AI enhanced context"]
        else:
            final_priority = heuristic_res['priority']
            final_category = heuristic_res['category']
            final_action = action_status
            importance_score = heuristic_res['importance_score']
            confidence = heuristic_res['confidence']
            reasons = heuristic_res['reasons']

    # Determine Review Status based on threshold
    if confidence >= settings.CONFIDENCE_AUTO_CLASSIFY:
        decision_status = "AUTO_CLASSIFIED"
    else:
        decision_status = "NEEDS_REVIEW"

    # Save Classification
    classification_entry = {
        "priority": final_priority,
        "action_status": final_action,
        "category": final_category,
        "importance_score": importance_score,
        "confidence": confidence,
        "status": decision_status,
        "reasons_json": json.dumps(reasons)
    }
    EmailRepository.save_classification(db, email_obj.id, classification_entry)

    target_labels = target_labels_for(
        final_priority, final_category, final_action, decision_status
    )

    return {
        "email_id": email_obj.id,
        "subject": email_obj.subject,
        "priority": final_priority,
        "category": final_category,
        "action_status": final_action,
        "confidence": confidence,
        "status": decision_status,
        "target_labels": target_labels
    }
