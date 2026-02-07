"""LLM-backed entity label suggestion.

Supports multiple backends via LITTERA_LLM_BACKEND env var:
  - lmstudio  — local LM Studio (OpenAI-compatible, localhost:1234)
  - anthropic — Anthropic Messages API (requires ANTHROPIC_API_KEY)
  - openai    — OpenAI Chat Completions (requires OPENAI_API_KEY)

When LITTERA_LLM_BACKEND is unset, no LLM calls are made (returns None).
All failures return None — callers decide how to present fallbacks.
"""

from __future__ import annotations

import json
import os
import urllib.request
import urllib.error


def suggest_label(
    canonical_label: str,
    entity_type: str,
    source_language: str,
    target_language: str,
) -> str | None:
    """Suggest a translated base form for an entity label.

    Returns the suggested translation or None if unavailable.
    Never raises — all errors are swallowed.
    """
    backend = os.environ.get("LITTERA_LLM_BACKEND")
    if not backend:
        return None

    system_prompt = (
        "You translate entity names between languages. "
        "Return ONLY the translated base form (dictionary form), nothing else."
    )
    user_prompt = (
        f'Translate the {entity_type} "{canonical_label}" '
        f"from {source_language} to {target_language}."
    )

    return _call_llm(backend, system_prompt, user_prompt)


def _call_llm(backend: str, system_prompt: str, user_prompt: str) -> str | None:
    """Dispatch to the appropriate backend. Returns stripped text or None."""
    try:
        if backend == "lmstudio":
            return _call_openai_compatible(
                url="http://localhost:1234/v1/chat/completions",
                api_key="lm-studio",
                system_prompt=system_prompt,
                user_prompt=user_prompt,
            )
        elif backend == "anthropic":
            return _call_anthropic(system_prompt, user_prompt)
        elif backend == "openai":
            return _call_openai_compatible(
                url="https://api.openai.com/v1/chat/completions",
                api_key=os.environ.get("OPENAI_API_KEY", ""),
                system_prompt=system_prompt,
                user_prompt=user_prompt,
            )
        else:
            return None
    except Exception:
        return None


def _call_openai_compatible(
    url: str, api_key: str, system_prompt: str, user_prompt: str
) -> str | None:
    """Call an OpenAI-compatible chat completions endpoint."""
    body = json.dumps({
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0.3,
        "max_tokens": 100,
    }).encode()

    req = urllib.request.Request(
        url,
        data=body,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
    )
    resp = urllib.request.urlopen(req, timeout=10)
    data = json.loads(resp.read())
    text = data["choices"][0]["message"]["content"].strip()
    return text if text else None


def _call_anthropic(system_prompt: str, user_prompt: str) -> str | None:
    """Call the Anthropic Messages API."""
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        return None

    body = json.dumps({
        "model": "claude-sonnet-4-5-20250514",
        "max_tokens": 100,
        "system": system_prompt,
        "messages": [{"role": "user", "content": user_prompt}],
    }).encode()

    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages",
        data=body,
        headers={
            "Content-Type": "application/json",
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
        },
    )
    resp = urllib.request.urlopen(req, timeout=10)
    data = json.loads(resp.read())
    text = data["content"][0]["text"].strip()
    return text if text else None
