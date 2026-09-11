from __future__ import annotations

import os
import re
import time
from collections import defaultdict, deque
from typing import Deque

from fastapi import HTTPException, Request

EMAIL = "bmaulanaa61@gmail.com"
DEFAULT_MAX_MESSAGE_CHARS = 500
DEFAULT_RATE_LIMIT_PER_MINUTE = 10

PHONE_PATTERN = re.compile(
    r"(?<!\w)(?:\+?62|0)(?:[\s().-]*\d){8,14}(?!\w)",
    re.IGNORECASE,
)
PROMPT_INJECTION_PATTERN = re.compile(
    r"(?:"
    r"\b(?:ignore|abaikan|lupakan|forget|bypass|override|disregard)\b.{0,50}\b(?:instructions?|instruksi|rules|aturan|prompt|guardrails?)\b"
    r"|\b(?:developer mode|jailbreak|system prompt|reveal prompt|expose prompt|leak prompt)\b"
    r"|\b(?:dan lupakan instruksi|mode pengembang|act as an unrestricted)\b"
    r")",
    re.IGNORECASE,
)
CONTROL_CHARS_PATTERN = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


def env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def parse_allowed_origins() -> list[str]:
    raw = os.getenv(
        "ALLOWED_ORIGINS",
        "http://localhost:3000,http://localhost:5173,https://datalabs-systems.web.app,https://datalabs-systems.firebaseapp.com",
    )
    return [item.strip().rstrip("/") for item in raw.split(",") if item.strip()]


def sanitize_message(message: str) -> str:
    max_chars = env_int("MAX_MESSAGE_CHARS", DEFAULT_MAX_MESSAGE_CHARS)
    cleaned = CONTROL_CHARS_PATTERN.sub(" ", message)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    if not cleaned:
        raise HTTPException(status_code=422, detail="Message is required.")
    if len(cleaned) > max_chars:
        raise HTTPException(status_code=413, detail=f"Message is too long. Maximum is {max_chars} characters.")
    return cleaned


def looks_like_prompt_injection(message: str) -> bool:
    return bool(PROMPT_INJECTION_PATTERN.search(message))


def privacy_filter(text: str) -> str:
    filtered = PHONE_PATTERN.sub("[nomor disembunyikan]", text)
    if "[nomor disembunyikan]" in filtered and EMAIL not in filtered:
        filtered += f"\n\nUntuk kontak profesional, gunakan email: {EMAIL}."
    return filtered


def get_client_ip(request: Request) -> str:
    cf_ip = request.headers.get("cf-connecting-ip")
    if cf_ip:
        return cf_ip.strip()
    real_ip = request.headers.get("x-real-ip")
    if real_ip:
        return real_ip.strip()
    forwarded_for = request.headers.get("x-forwarded-for", "")
    if forwarded_for:
        return forwarded_for.split(",", 1)[0].strip()
    if request.client:
        return request.client.host
    return "unknown"


class InMemoryRateLimiter:
    def __init__(self, limit_per_minute: int | None = None):
        self.limit_per_minute = limit_per_minute or env_int("RATE_LIMIT_PER_MINUTE", DEFAULT_RATE_LIMIT_PER_MINUTE)
        self._hits: dict[str, Deque[float]] = defaultdict(deque)

    def _prune(self, now: float) -> None:
        window_start = now - 60
        stale_keys = [k for k, timestamps in self._hits.items() if not timestamps or timestamps[-1] < window_start]
        for k in stale_keys:
            del self._hits[k]

    def check(self, key: str) -> None:
        now = time.monotonic()
        if len(self._hits) > 200:
            self._prune(now)

        window_start = now - 60
        hits = self._hits[key]
        while hits and hits[0] < window_start:
            hits.popleft()
        if len(hits) >= self.limit_per_minute:
            raise HTTPException(status_code=429, detail="Too many requests. Please try again later.")
        hits.append(now)

    def reset(self) -> None:
        self._hits.clear()
