from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any, Dict, List, Optional

from config import settings

GEMINI_CLASSIFY_PROMPT = """You are an expert email classification AI.
Analyze the email and return strict JSON only:

Sender: {sender}
Subject: {subject}
Content: {body}

Return JSON:
{{
  "priority": "URGENT" | "IMPORTANT" | "NORMAL" | "LOW_PRIORITY",
  "category": "WORK" | "UNIVERSITY" | "CAREER" | "FINANCE" | "PERSONAL" | "NEWSLETTER" | "PROMOTION" | "NOTIFICATION" | "OTHER",
  "action_status": "ACTION_REQUIRED" | "WAITING_FOR_REPLY" | "NO_ACTION" | "FOLLOW_UP",
  "importance_score": float 0-100,
  "confidence": float 0.0-1.0,
  "reasons": [string],
  "extracted_deadline": null or "YYYY-MM-DD",
  "extracted_action": null or string
}}
"""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def gemini_configured() -> bool:
    return bool((settings.GEMINI_API_KEY or "").strip())


def groq_configured() -> bool:
    return bool((settings.GROQ_API_KEY or "").strip())


def _strip_think(text: str) -> str:
    if not text:
        return ""
    out = text
    while "<think>" in out and "</think>" in out:
        start = out.find("<think>")
        end = out.find("</think>") + len("</think>")
        out = (out[:start] + out[end:]).strip()
    return out.strip()


def _parse_json_object(text: str) -> Optional[Dict[str, Any]]:
    raw = _strip_think(text).strip()
    if raw.startswith("```json"):
        raw = raw[7:]
    if raw.startswith("```"):
        raw = raw[3:]
    if raw.endswith("```"):
        raw = raw[:-3]
    raw = raw.strip()
    try:
        data = json.loads(raw)
        return data if isinstance(data, dict) else None
    except json.JSONDecodeError:
        start = raw.find("{")
        end = raw.rfind("}")
        if start >= 0 and end > start:
            try:
                data = json.loads(raw[start : end + 1])
                return data if isinstance(data, dict) else None
            except json.JSONDecodeError:
                return None
    return None


# ---------------------------------------------------------------------------
# Gemini
# ---------------------------------------------------------------------------

def generate_gemini(prompt: str, system: Optional[str] = None) -> Optional[str]:
    if not gemini_configured():
        return None
    try:
        from google import genai
        from google.genai import types
    except ImportError:
        return None
    try:
        client = genai.Client(api_key=settings.GEMINI_API_KEY)
        config = types.GenerateContentConfig(
            system_instruction=system,
            temperature=0.3,
        ) if system else None
        
        model_list = []
        if hasattr(settings, "GEMINI_MODELS") and settings.GEMINI_MODELS:
            model_list = [m.strip() for m in settings.GEMINI_MODELS.split(",") if m.strip()]
        else:
            model_list = [settings.GEMINI_MODEL]
            
        for model in model_list:
            try:
                response = client.models.generate_content(
                    model=model,
                    contents=prompt,
                    config=config,
                )
                text = (response.text or "").strip()
                if text:
                    print(f"[LLM] Gemini/{model} responded")
                    return text
            except Exception as exc:
                print(f"[LLM] Gemini/{model} skipped: {type(exc).__name__} - {exc}")
                
        return None
    except Exception as exc:
        print(f"[LLM] Gemini client error: {type(exc).__name__} - {exc}")
        return None


# ---------------------------------------------------------------------------
# Groq Cloud (OpenAI-compatible)
# ---------------------------------------------------------------------------

def _groq_chat(model: str, messages: List[Dict[str, str]], timeout: int = 60) -> Optional[str]:
    """Low-level call to Groq's OpenAI-compatible /chat/completions endpoint."""
    url = settings.GROQ_BASE_URL.rstrip("/") + "/chat/completions"
    body = json.dumps({
        "model": model,
        "messages": messages,
        "temperature": 0.3,
    }).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=body,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {settings.GROQ_API_KEY}",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
        text = (payload.get("choices", [{}])[0]
                .get("message", {})
                .get("content", "")).strip()
        return _strip_think(text) or None
    except urllib.error.HTTPError as exc:
        body_bytes = exc.read()
        try:
            err = json.loads(body_bytes).get("error", {})
            print(f"[LLM] Groq/{model} HTTP {exc.code}: {err.get('message', exc.reason)}")
        except Exception:
            print(f"[LLM] Groq/{model} HTTP {exc.code}: {exc.reason}")
        return None
    except Exception as exc:
        print(f"[LLM] Groq/{model} skipped: {type(exc).__name__}")
        return None


def generate_groq(
    prompt: str,
    system: Optional[str] = None,
    timeout: int = 60,
) -> Optional[str]:
    """Try each model in GROQ_TEXT_MODELS in order. Return first successful response."""
    if not groq_configured():
        return None

    model_list = [m.strip() for m in settings.GROQ_TEXT_MODELS.split(",") if m.strip()]
    messages: List[Dict[str, str]] = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    for model in model_list:
        text = _groq_chat(model, messages, timeout=timeout)
        if text:
            print(f"[LLM] Groq/{model} responded")
            return text

    return None


# ---------------------------------------------------------------------------
# Ollama local
# ---------------------------------------------------------------------------

def ollama_reachable() -> bool:
    if not settings.OLLAMA_ENABLED:
        return False
    url = settings.OLLAMA_BASE_URL.rstrip("/") + "/api/tags"
    try:
        with urllib.request.urlopen(url, timeout=2) as resp:
            return resp.status == 200
    except Exception:
        return False


def ollama_has_model() -> bool:
    if not settings.OLLAMA_ENABLED:
        return False
    url = settings.OLLAMA_BASE_URL.rstrip("/") + "/api/tags"
    try:
        with urllib.request.urlopen(url, timeout=2) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
        names = [m.get("name", "") for m in payload.get("models", [])]
        target = settings.OLLAMA_MODEL
        return any(name == target or name.startswith(target.split(":")[0]) for name in names)
    except Exception:
        return False


def generate_ollama(prompt: str, system: Optional[str] = None, timeout: int = 90) -> Optional[str]:
    if not settings.OLLAMA_ENABLED:
        return None
    url = settings.OLLAMA_BASE_URL.rstrip("/") + "/api/chat"
    messages: List[Dict[str, str]] = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})
    body = json.dumps({
        "model": settings.OLLAMA_MODEL,
        "messages": messages,
        "stream": False,
        "options": {"temperature": 0.3},
    }).encode("utf-8")
    req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
        text = ((payload.get("message") or {}).get("content") or "").strip()
        return _strip_think(text) or None
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError) as exc:
        print(f"[LLM] Ollama skipped: {type(exc).__name__}")
        return None


# ---------------------------------------------------------------------------
# High-level task functions  — fallback chain
# Gemini → Groq (compound → compound-mini → qwen → gpt-oss-120b → gpt-oss-20b) → Ollama
# ---------------------------------------------------------------------------

def classify_email_with_llm(subject: str, sender: str, body: str) -> Optional[Dict[str, Any]]:
    prompt = GEMINI_CLASSIFY_PROMPT.format(sender=sender, subject=subject, body=(body or "")[:1500])

    # 1. Groq — tries all GROQ_TEXT_MODELS sequentially
    text = generate_groq(
        prompt,
        system="Return valid JSON only. No markdown. No explanation.",
    )

    # 2. Gemini
    if not text:
        text = generate_gemini(prompt)

    # 3. Ollama local
    if not text:
        text = generate_ollama(
            prompt,
            system="Return valid JSON only. No markdown.",
            timeout=60,
        )

    if not text:
        return None
    return _parse_json_object(text)


def polish_coworker_reply(user_message: str, facts: Dict[str, Any]) -> Optional[str]:
    compact = json.dumps(facts, ensure_ascii=False)[:5000]
    system = (
        "You are a professional inbox coworker. Write concise Vietnamese unless the user used English. "
        "Use only the provided JSON facts. Do not invent emails. "
        "If dry_run is true, say labels are simulated. End by asking to confirm labels when cards exist."
    )
    prompt = f"User: {user_message}\nFacts JSON:\n{compact}"

    # 1. Groq (fast cloud)
    text = generate_groq(prompt, system=system, timeout=30)
    if text and len(text) > 20:
        return text

    # 2. Gemini fallback
    text = generate_gemini(prompt, system=system)
    if text and len(text) > 20:
        return text

    # 3. Ollama (short timeout to avoid blocking UI)
    text = generate_ollama(prompt, system=system, timeout=30)
    if text and len(text) > 20:
        return text

    return None


# ---------------------------------------------------------------------------
# Status report
# ---------------------------------------------------------------------------

def llm_status() -> Dict[str, Any]:
    ollama_up = ollama_reachable()
    ollama_model = ollama_has_model() if ollama_up else False
    gemini_on = gemini_configured()
    groq_on = groq_configured()

    if groq_on:
        active = "groq"
    elif gemini_on:
        active = "gemini"
    elif ollama_up and ollama_model:
        active = "ollama"
    else:
        active = "heuristic"

    groq_models = [m.strip() for m in settings.GROQ_TEXT_MODELS.split(",") if m.strip()]

    return {
        "active": active,
        "fallback_chain": ["groq", "gemini", "ollama", "heuristic"],
        "gemini": {
            "configured": gemini_on,
            "ok": gemini_on,
            "model": settings.GEMINI_MODEL,
        },
        "groq": {
            "configured": groq_on,
            "base_url": settings.GROQ_BASE_URL,
            "text_models": groq_models,
            "stt_enabled": settings.GROQ_STT_ENABLED,
            "stt_model": settings.GROQ_STT_MODEL,
            "tts_enabled": settings.GROQ_TTS_ENABLED,
            "tts_model": settings.GROQ_TTS_MODEL,
        },
        "ollama": {
            "enabled": settings.OLLAMA_ENABLED,
            "reachable": ollama_up,
            "model": settings.OLLAMA_MODEL,
            "model_present": ollama_model,
            "base_url": settings.OLLAMA_BASE_URL,
        },
    }
