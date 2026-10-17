from typing import Optional, Dict, Any

from classification.llm_providers import classify_email_with_llm


def analyze_with_gemini(subject: str, sender: str, body: str) -> Optional[Dict[str, Any]]:
    """Classify with Gemini, then local Qwen via Ollama."""
    return classify_email_with_llm(subject, sender, body)
