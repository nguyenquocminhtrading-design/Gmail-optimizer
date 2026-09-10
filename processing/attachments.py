import os
from typing import List, Dict, Any

def classify_attachment(filename: str, mime_type: str) -> str:
    ext = os.path.splitext(filename)[1].lower()
    
    if ext in ['.pdf', '.doc', '.docx'] and any(kw in filename.lower() for kw in ['statement', 'invoice', 'receipt', 'tax', 'financial', 'bank']):
        return "FINANCIAL"
    elif ext in ['.pdf', '.doc', '.docx'] and any(kw in filename.lower() for kw in ['contract', 'agreement', 'offer', 'nda']):
        return "CONTRACT"
    elif ext in ['.pdf', '.doc', '.docx', '.ppt', '.pptx']:
        return "DOCUMENT"
    elif ext in ['.xls', '.xlsx', '.csv']:
        return "FINANCIAL" if any(kw in filename.lower() for kw in ['fs', 'finance', 'budget', 'statement']) else "REPORT"
    elif ext in ['.png', '.jpg', '.jpeg', '.gif']:
        return "IMAGE"
    elif ext in ['.zip', '.rar', '.7z', '.tar', '.gz']:
        return "ARCHIVE"
    else:
        return "OTHER"
