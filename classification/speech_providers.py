"""
speech_providers.py
~~~~~~~~~~~~~~~~~~~~
Groq Cloud Speech-to-Text (Whisper) and Text-to-Speech (Orpheus) providers.

Both features are disabled by default; enable via .env:
    GROQ_STT_ENABLED=True
    GROQ_TTS_ENABLED=True
"""
from __future__ import annotations

import io
import json
import urllib.error
import urllib.request
from typing import Optional

from config import settings


# ---------------------------------------------------------------------------
# Speech-to-Text — Groq Whisper
# ---------------------------------------------------------------------------

def transcribe_audio(audio_bytes: bytes, filename: str = "audio.wav") -> Optional[str]:
    """
    Transcribe audio using Groq Whisper API.

    Args:
        audio_bytes: Raw audio file content (wav, mp3, m4a, ogg, flac…)
        filename:    Original filename — Groq uses the extension to detect codec.

    Returns:
        Transcribed text string, or None on failure / disabled.
    """
    if not settings.GROQ_STT_ENABLED:
        print("[STT] Groq STT is disabled (GROQ_STT_ENABLED=False)")
        return None
    if not (settings.GROQ_API_KEY or "").strip():
        print("[STT] GROQ_API_KEY not set")
        return None

    url = settings.GROQ_BASE_URL.rstrip("/") + "/audio/transcriptions"

    # Build multipart/form-data manually (no external deps)
    boundary = "----GmailOptimizerBoundary"
    body_parts: list[bytes] = []

    def _field(name: str, value: str) -> bytes:
        return (
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="{name}"\r\n\r\n'
            f"{value}\r\n"
        ).encode("utf-8")

    def _file_field(name: str, fname: str, data: bytes, mime: str) -> bytes:
        header = (
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="{name}"; filename="{fname}"\r\n'
            f"Content-Type: {mime}\r\n\r\n"
        ).encode("utf-8")
        return header + data + b"\r\n"

    # Guess MIME type from extension
    ext = filename.rsplit(".", 1)[-1].lower()
    mime_map = {
        "mp3": "audio/mpeg", "wav": "audio/wav", "m4a": "audio/mp4",
        "ogg": "audio/ogg", "flac": "audio/flac", "webm": "audio/webm",
    }
    mime = mime_map.get(ext, "application/octet-stream")

    body_parts.append(_field("model", settings.GROQ_STT_MODEL))
    body_parts.append(_field("response_format", "json"))
    body_parts.append(_file_field("file", filename, audio_bytes, mime))
    body_parts.append(f"--{boundary}--\r\n".encode("utf-8"))

    body = b"".join(body_parts)
    req = urllib.request.Request(
        url,
        data=body,
        headers={
            "Authorization": f"Bearer {settings.GROQ_API_KEY}",
            "Content-Type": f"multipart/form-data; boundary={boundary}",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
        text = payload.get("text", "").strip()
        if text:
            print(f"[STT] Groq Whisper transcribed {len(audio_bytes)} bytes → {len(text)} chars")
        return text or None
    except urllib.error.HTTPError as exc:
        try:
            err = json.loads(exc.read()).get("error", {})
            print(f"[STT] Groq Whisper HTTP {exc.code}: {err.get('message', exc.reason)}")
        except Exception:
            print(f"[STT] Groq Whisper HTTP {exc.code}: {exc.reason}")
        return None
    except Exception as exc:
        print(f"[STT] Groq Whisper error: {type(exc).__name__} - {exc}")
        return None


# ---------------------------------------------------------------------------
# Text-to-Speech — Groq Orpheus
# ---------------------------------------------------------------------------

def speak_text(text: str, voice: Optional[str] = None) -> Optional[bytes]:
    """
    Synthesise speech from text using Groq Orpheus TTS API.

    Args:
        text:  The text to synthesise (max ~500 tokens recommended).
        voice: Optional voice name (model-specific). Defaults to None (provider default).

    Returns:
        Raw audio bytes (mp3), or None on failure / disabled.
    """
    if not settings.GROQ_TTS_ENABLED:
        print("[TTS] Groq TTS is disabled (GROQ_TTS_ENABLED=False)")
        return None
    if not (settings.GROQ_API_KEY or "").strip():
        print("[TTS] GROQ_API_KEY not set")
        return None

    url = settings.GROQ_BASE_URL.rstrip("/") + "/audio/speech"
    payload: dict = {
        "model": settings.GROQ_TTS_MODEL,
        "input": text,
        "response_format": "mp3",
    }
    if voice:
        payload["voice"] = voice

    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=body,
        headers={
            "Authorization": f"Bearer {settings.GROQ_API_KEY}",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            audio_bytes = resp.read()
        print(f"[TTS] Groq Orpheus synthesised {len(text)} chars → {len(audio_bytes)} bytes")
        return audio_bytes
    except urllib.error.HTTPError as exc:
        try:
            err = json.loads(exc.read()).get("error", {})
            print(f"[TTS] Groq Orpheus HTTP {exc.code}: {err.get('message', exc.reason)}")
        except Exception:
            print(f"[TTS] Groq Orpheus HTTP {exc.code}: {exc.reason}")
        return None
    except Exception as exc:
        print(f"[TTS] Groq Orpheus error: {type(exc).__name__} - {exc}")
        return None
