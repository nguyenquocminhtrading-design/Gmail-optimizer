import json
from config import settings
from typing import Optional, Dict, Any

def analyze_with_gemini(subject: str, sender: str, body: str) -> Optional[Dict[str, Any]]:
    if not settings.GEMINI_API_KEY:
        return None

    try:
        from google import genai
        client = genai.Client(api_key=settings.GEMINI_API_KEY)
        
        prompt = f"""
You are an expert email classification and metadata extraction AI.
Analyze the following email and return strict JSON format:

Sender: {sender}
Subject: {subject}
Content: {body[:1500]}

Return JSON format strictly:
{{
  "priority": "URGENT" | "IMPORTANT" | "NORMAL" | "LOW_PRIORITY",
  "category": "WORK" | "UNIVERSITY" | "CAREER" | "FINANCE" | "PERSONAL" | "NEWSLETTER" | "PROMOTION" | "NOTIFICATION" | "OTHER",
  "action_status": "ACTION_REQUIRED" | "WAITING_FOR_REPLY" | "NO_ACTION" | "FOLLOW_UP",
  "importance_score": float 0-100,
  "confidence": float 0.0-1.0,
  "reasons": [list of string explanations],
  "extracted_deadline": null or "YYYY-MM-DD",
  "extracted_action": null or string description
}}
"""
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt
        )
        
        text_out = response.text.strip()
        # Clean potential markdown block formatting
        if text_out.startswith("```json"):
            text_out = text_out[7:]
        if text_out.endswith("```"):
            text_out = text_out[:-3]
        
        data = json.loads(text_out.strip())
        return data
    except Exception as e:
        print(f"Gemini API classification skipped/error: {e}")
        return None
