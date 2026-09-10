import base64
import email.utils
import datetime
from googleapiclient.discovery import Resource
from typing import Dict, Any, List, Optional

def parse_header(headers: List[dict], name: str) -> str:
    for h in headers:
        if h.get('name', '').lower() == name.lower():
            return h.get('value', '')
    return ''

def decode_body_part(part: dict) -> str:
    data = part.get('body', {}).get('data', '')
    if not data:
        return ''
    try:
        decoded_bytes = base64.urlsafe_b64decode(data.encode('ASCII'))
        return decoded_bytes.decode('utf-8', errors='replace')
    except Exception as e:
        print(f"Error decoding body part: {e}")
        return ''

def extract_message_content(payload: dict) -> tuple[str, str, list]:
    plain_text = ""
    html_text = ""
    attachments = []

    def walk_parts(parts):
        nonlocal plain_text, html_text, attachments
        for part in parts:
            mime_type = part.get('mimeType', '')
            filename = part.get('filename', '')
            body = part.get('body', {})
            
            if filename:
                size = body.get('size', 0)
                attachments.append({
                    'filename': filename,
                    'mime_type': mime_type,
                    'size_bytes': size
                })
            elif mime_type == 'text/plain':
                plain_text += decode_body_part(part)
            elif mime_type == 'text/html':
                html_text += decode_body_part(part)
            
            if 'parts' in part:
                walk_parts(part['parts'])

    if 'parts' in payload:
        walk_parts(payload['parts'])
    else:
        mime_type = payload.get('mimeType', '')
        if mime_type == 'text/plain':
            plain_text = decode_body_part(payload)
        elif mime_type == 'text/html':
            html_text = decode_body_part(payload)

    return plain_text, html_text, attachments

def fetch_email_details(service: Resource, message_id: str) -> Dict[str, Any]:
    msg = service.users().messages().get(userId='me', id=message_id, format='full').execute()
    
    payload = msg.get('payload', {})
    headers = payload.get('headers', [])
    
    subject = parse_header(headers, 'Subject') or '(No Subject)'
    from_header = parse_header(headers, 'From')
    to_header = parse_header(headers, 'To')
    date_header = parse_header(headers, 'Date')

    sender_name, sender_email = email.utils.parseaddr(from_header)
    if not sender_email:
        sender_email = from_header or 'unknown@domain.com'
        sender_name = sender_email

    # Date parsing
    parsed_date = None
    if date_header:
        try:
            parsed_tuple = email.utils.parsedate_tz(date_header)
            if parsed_tuple:
                timestamp = email.utils.mktime_tz(parsed_tuple)
                parsed_date = datetime.datetime.fromtimestamp(timestamp, tz=datetime.timezone.utc).replace(tzinfo=None)
        except Exception:
            pass
    if not parsed_date:
        parsed_date = datetime.datetime.utcnow()

    plain_text, html_text, attachments = extract_message_content(payload)
    label_ids = msg.get('labelIds', [])
    is_read = 'UNREAD' not in label_ids

    return {
        'gmail_message_id': msg['id'],
        'thread_id': msg['threadId'],
        'sender_name': sender_name,
        'sender_email': sender_email.lower(),
        'recipient': to_header,
        'subject': subject,
        'date_received': parsed_date,
        'body_plain': plain_text,
        'body_html': html_text,
        'is_read': is_read,
        'has_attachments': len(attachments) > 0,
        'attachments': attachments,
        'existing_labels': ','.join(label_ids)
    }

def fetch_recent_message_ids(service: Resource, max_results: int = 50, query: str = "") -> List[str]:
    response = service.users().messages().list(userId='me', maxResults=max_results, q=query).execute()
    messages = response.get('messages', [])
    return [m['id'] for m in messages]
