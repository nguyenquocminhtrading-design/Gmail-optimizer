from googleapiclient.discovery import Resource
from typing import Dict, List

DEFAULT_AI_LABELS = [
    "AI/Urgent",
    "AI/Important",
    "AI/Action Required",
    "AI/Review",
    "AI/Career",
    "AI/Finance",
    "AI/University",
    "AI/Work",
    "AI/Personal",
    "AI/Newsletter",
    "AI/Low Priority"
]

class LabelManager:
    def __init__(self, service: Resource):
        self.service = service
        self.label_map: Dict[str, str] = {} # Name -> Label ID

    def sync_labels(self) -> Dict[str, str]:
        """Fetch existing Gmail labels and create missing AI/* labels safely."""
        response = self.service.users().labels().list(userId='me').execute()
        existing = response.get('labels', [])
        
        for lbl in existing:
            self.label_map[lbl['name']] = lbl['id']

        for target_label in DEFAULT_AI_LABELS:
            if target_label not in self.label_map:
                created_label = self._create_label(target_label)
                if created_label:
                    self.label_map[target_label] = created_label['id']
                    
        return self.label_map

    def _create_label(self, label_name: str) -> dict | None:
        label_object = {
            'name': label_name,
            'labelListVisibility': 'labelShow',
            'messageListVisibility': 'show'
        }
        try:
            return self.service.users().labels().create(userId='me', body=label_object).execute()
        except Exception as e:
            print(f"Failed to create label {label_name}: {e}")
            return None

    def apply_labels_to_message(self, message_id: str, label_names: List[str], dry_run: bool = True):
        if dry_run:
            print(f"[DRY RUN] Would apply labels {label_names} to message {message_id}")
            return

        add_label_ids = [self.label_map[name] for name in label_names if name in self.label_map]
        if not add_label_ids:
            return

        body = {'addLabelIds': add_label_ids}
        try:
            self.service.users().messages().modify(userId='me', id=message_id, body=body).execute()
        except Exception as e:
            print(f"Error applying labels to message {message_id}: {e}")

    def archive_message(self, message_id: str, dry_run: bool = True):
        if dry_run:
            print(f"[DRY RUN] Would archive message {message_id}")
            return

        body = {'removeLabelIds': ['INBOX']}
        try:
            self.service.users().messages().modify(userId='me', id=message_id, body=body).execute()
        except Exception as e:
            print(f"Error archiving message {message_id}: {e}")
