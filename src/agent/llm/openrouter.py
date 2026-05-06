from collections.abc import Sequence

import httpx

from agent.config import get_settings


class OpenRouterError(RuntimeError):
    """Raised when OpenRouter cannot produce a usable chat completion."""


def _content_to_text(content: object) -> str:
    if isinstance(content, str):
        return content.strip()

    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
                continue
            if not isinstance(item, dict):
                continue
            text = item.get("text")
            if isinstance(text, str):
                parts.append(text)
                continue
            nested_text = item.get("content")
            if isinstance(nested_text, str):
                parts.append(nested_text)
        return "\n".join(part.strip() for part in parts if part.strip())

    if isinstance(content, dict):
        text = content.get("text") or content.get("content")
        if isinstance(text, str):
            return text.strip()

    return ""


def chat_completion(
    messages: Sequence[dict[str, str]],
    *,
    max_tokens: int,
    temperature: float = 0.2,
    model: str | None = None,
    session_id: str | None = None,
) -> str:
    settings = get_settings()
    if not settings.openrouter_api_key:
        raise OpenRouterError("OPENROUTER_API_KEY is required to call OpenRouter")

    url = f"{settings.openrouter_base_url.rstrip('/')}/chat/completions"
    headers = {
        "Authorization": f"Bearer {settings.openrouter_api_key}",
        "Content-Type": "application/json",
        "X-OpenRouter-Title": settings.openrouter_app_title,
    }
    if settings.openrouter_app_url:
        headers["HTTP-Referer"] = settings.openrouter_app_url

    payload: dict[str, object] = {
        "model": model or settings.openrouter_model,
        "messages": list(messages),
        "max_tokens": max_tokens,
        "temperature": temperature,
    }
    if session_id:
        payload["session_id"] = session_id

    try:
        with httpx.Client(timeout=60) as client:
            response = client.post(url, headers=headers, json=payload)
            response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        raise OpenRouterError(
            f"OpenRouter request failed with status {exc.response.status_code}: "
            f"{exc.response.text[:500]}"
        ) from exc
    except httpx.HTTPError as exc:
        raise OpenRouterError("OpenRouter request failed") from exc

    try:
        data = response.json()
    except ValueError as exc:
        raise OpenRouterError("OpenRouter response was not valid JSON") from exc
    try:
        content = data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise OpenRouterError("OpenRouter response did not contain message content") from exc

    text = _content_to_text(content)
    if text:
        return text
    raise OpenRouterError("OpenRouter response content was empty or unsupported")
