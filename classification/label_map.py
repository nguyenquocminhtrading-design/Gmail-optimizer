from typing import List, Optional


def target_labels_for(
    priority: Optional[str],
    category: Optional[str],
    action_status: Optional[str],
    decision_status: Optional[str] = None,
) -> List[str]:
    """Map a classification to the AI/* Gmail label namespace."""
    labels: List[str] = []
    priority = (priority or "").upper()
    category = (category or "").upper()
    action_status = (action_status or "").upper()
    decision_status = (decision_status or "").upper()

    if priority == "URGENT":
        labels.append("AI/Urgent")
    elif priority == "IMPORTANT":
        labels.append("AI/Important")
    elif priority == "LOW_PRIORITY":
        labels.append("AI/Low Priority")

    if action_status == "ACTION_REQUIRED":
        labels.append("AI/Action Required")

    if category in ["CAREER", "FINANCE", "UNIVERSITY", "WORK", "NEWSLETTER", "PERSONAL"]:
        labels.append(f"AI/{category.capitalize()}")

    if decision_status == "NEEDS_REVIEW":
        labels.append("AI/Review")

    return labels
