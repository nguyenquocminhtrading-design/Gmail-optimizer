import datetime
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func, desc, or_, and_
from typing import List, Optional, Dict, Any
from database.models import (
    EmailModel, ClassificationModel, DeadlineModel,
    ActionModel, AttachmentModel, UserFeedbackModel, RuleModel, SyncStateModel
)

class EmailRepository:

    @staticmethod
    def get_by_gmail_id(db: Session, gmail_id: str) -> Optional[EmailModel]:
        return db.query(EmailModel).filter(EmailModel.gmail_message_id == gmail_id).first()

    @staticmethod
    def create_email(db: Session, email_data: dict) -> EmailModel:
        email = EmailModel(**email_data)
        db.add(email)
        db.commit()
        db.refresh(email)
        return email

    @staticmethod
    def save_classification(db: Session, email_id: int, classification_data: dict) -> ClassificationModel:
        existing = db.query(ClassificationModel).filter(ClassificationModel.email_id == email_id).first()
        if existing:
            for k, v in classification_data.items():
                setattr(existing, k, v)
            db.commit()
            db.refresh(existing)
            return existing
        else:
            cls = ClassificationModel(email_id=email_id, **classification_data)
            db.add(cls)
            db.commit()
            db.refresh(cls)
            return cls

    @staticmethod
    def add_deadline(db: Session, email_id: int, title: str, deadline_date: datetime.datetime, is_relative: bool = False, confidence: float = 1.0) -> DeadlineModel:
        dl = DeadlineModel(
            email_id=email_id,
            title=title,
            deadline_date=deadline_date,
            is_relative=is_relative,
            confidence=confidence
        )
        db.add(dl)
        db.commit()
        db.refresh(dl)
        return dl

    @staticmethod
    def add_action(db: Session, email_id: int, action_description: str, priority: str = "NORMAL") -> ActionModel:
        act = ActionModel(
            email_id=email_id,
            action_description=action_description,
            priority=priority
        )
        db.add(act)
        db.commit()
        db.refresh(act)
        return act

    @staticmethod
    def add_attachment(db: Session, email_id: int, filename: str, mime_type: str, size_bytes: int, relevance_category: str) -> AttachmentModel:
        att = AttachmentModel(
            email_id=email_id,
            filename=filename,
            mime_type=mime_type,
            size_bytes=size_bytes,
            relevance_category=relevance_category
        )
        db.add(att)
        db.commit()
        db.refresh(att)
        return att

    @staticmethod
    def get_review_queue(db: Session, limit: int = 50) -> List[EmailModel]:
        return (
            db.query(EmailModel)
            .join(ClassificationModel)
            .filter(ClassificationModel.status == "NEEDS_REVIEW")
            .options(joinedload(EmailModel.classification), joinedload(EmailModel.deadlines), joinedload(EmailModel.actions))
            .order_by(desc(EmailModel.date_received))
            .limit(limit)
            .all()
        )

    @staticmethod
    def get_today_important_emails(db: Session, limit: int = 50) -> List[EmailModel]:
        return (
            db.query(EmailModel)
            .join(ClassificationModel)
            .filter(ClassificationModel.priority.in_(["URGENT", "IMPORTANT"]))
            .options(joinedload(EmailModel.classification), joinedload(EmailModel.deadlines), joinedload(EmailModel.actions))
            .order_by(desc(EmailModel.date_received))
            .limit(limit)
            .all()
        )

    @staticmethod
    def get_emails_with_deadlines(db: Session, limit: int = 20) -> List[Dict[str, Any]]:
        now = datetime.datetime.utcnow()
        deadlines = (
            db.query(DeadlineModel)
            .join(EmailModel)
            .options(joinedload(DeadlineModel.email).joinedload(EmailModel.classification))
            .filter(DeadlineModel.deadline_date >= now - datetime.timedelta(days=1))
            .order_by(DeadlineModel.deadline_date.asc())
            .limit(limit)
            .all()
        )
        return deadlines

    @staticmethod
    def record_user_feedback(
        db: Session,
        email_id: int,
        new_priority: str,
        new_category: str,
        new_action: str,
        scope: str = "THIS_EMAIL",
        reason: Optional[str] = None
    ) -> UserFeedbackModel:
        email = db.query(EmailModel).filter(EmailModel.id == email_id).first()
        if not email:
            raise ValueError(f"Email ID {email_id} not found")

        old_priority = email.classification.priority if email.classification else None
        old_category = email.classification.category if email.classification else None
        old_action = email.classification.action_status if email.classification else None

        # 1. Update email classification status to USER_REVIEWED
        if email.classification:
            email.classification.priority = new_priority
            email.classification.category = new_category
            email.classification.action_status = new_action
            email.classification.status = "USER_REVIEWED"
            email.classification.confidence = 1.0

        # 2. Record feedback entry
        feedback = UserFeedbackModel(
            email_id=email_id,
            old_priority=old_priority,
            new_priority=new_priority,
            old_category=old_category,
            new_category=new_category,
            old_action=old_action,
            new_action=new_action,
            scope=scope,
            reason=reason
        )
        db.add(feedback)

        # 3. Create or update rules according to selected scope
        if scope in ["THIS_SENDER", "SIMILAR_SUBJECTS"]:
            condition_type = "SENDER" if scope == "THIS_SENDER" else "SUBJECT_CONTAINS"
            condition_value = email.sender_email.lower() if scope == "THIS_SENDER" else email.subject.lower()[:50]

            rule = RuleModel(
                rule_type="LEARNED_PREFERENCE",
                condition_type=condition_type,
                condition_value=condition_value,
                target_priority=new_priority,
                target_category=new_category,
                target_action=new_action,
                never_archive=(new_priority in ["URGENT", "IMPORTANT"])
            )
            db.add(rule)

        db.commit()
        db.refresh(feedback)
        return feedback

    @staticmethod
    def get_dashboard_stats(db: Session) -> Dict[str, Any]:
        total_emails = db.query(func.count(EmailModel.id)).scalar() or 0
        important_today = (
            db.query(func.count(EmailModel.id))
            .join(ClassificationModel)
            .filter(ClassificationModel.priority.in_(["URGENT", "IMPORTANT"]))
            .scalar() or 0
        )
        action_required = (
            db.query(func.count(EmailModel.id))
            .join(ClassificationModel)
            .filter(ClassificationModel.action_status == "ACTION_REQUIRED")
            .scalar() or 0
        )
        urgent_count = (
            db.query(func.count(EmailModel.id))
            .join(ClassificationModel)
            .filter(ClassificationModel.priority == "URGENT")
            .scalar() or 0
        )
        needs_review_count = (
            db.query(func.count(EmailModel.id))
            .join(ClassificationModel)
            .filter(ClassificationModel.status == "NEEDS_REVIEW")
            .scalar() or 0
        )
        upcoming_deadlines_count = db.query(func.count(DeadlineModel.id)).scalar() or 0

        return {
            "total_emails": total_emails,
            "important_today": important_today,
            "action_required": action_required,
            "urgent": urgent_count,
            "needs_review": needs_review_count,
            "upcoming_deadlines": upcoming_deadlines_count
        }

    @staticmethod
    def get_sender_stats(db: Session, sender_email: str) -> Dict[str, Any]:
        emails = db.query(EmailModel).filter(EmailModel.sender_email == sender_email.lower()).all()
        if not emails:
            return {"count": 0, "avg_importance": 50.0, "is_frequent": False}
        
        count = len(emails)
        scores = [e.classification.importance_score for e in emails if e.classification]
        avg_score = sum(scores) / len(scores) if scores else 50.0

        return {
            "count": count,
            "avg_importance": avg_score,
            "is_frequent": count >= 3
        }

    @staticmethod
    def get_all_rules(db: Session) -> List[RuleModel]:
        return db.query(RuleModel).order_by(desc(RuleModel.created_at)).all()
