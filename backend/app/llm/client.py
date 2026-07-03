"""LLM client — dispatches to the deterministic mock or a real Cerebras call.

Real calls go through LiteLLM → OpenRouter to ``openrouter/openai/gpt-oss-120b``
with Cerebras pinned as the inference provider and structured outputs requested
(per the `cerebras` skill). The call is synchronous; the chat endpoint runs it in
a threadpool so it never blocks the event loop.
"""

from __future__ import annotations

import logging
import os

from .prompt import build_messages
from .schema import LLMResponse, parse_llm_response

logger = logging.getLogger(__name__)

MODEL = "openrouter/openai/gpt-oss-120b"
EXTRA_BODY = {"provider": {"order": ["cerebras"]}}

_ERROR_FALLBACK = (
    "I'm having trouble reaching the AI service right now, so I didn't make any changes. "
    "Please try again in a moment."
)


def is_mock_enabled() -> bool:
    """True when ``LLM_MOCK`` is set truthy in the environment."""
    return os.getenv("LLM_MOCK", "false").strip().lower() in ("1", "true", "yes", "on")


def _call_cerebras(messages: list[dict]) -> LLMResponse:
    """Perform the real structured-output completion. Imported lazily so the
    module (and tests) don't require litellm/network unless a real call happens."""
    from litellm import completion

    response = completion(
        model=MODEL,
        messages=messages,
        response_format=LLMResponse,
        reasoning_effort="low",
        extra_body=EXTRA_BODY,
    )
    raw = response.choices[0].message.content
    return parse_llm_response(raw)


def generate_response(
    user_message: str,
    portfolio_state: dict | None = None,
    watchlist_context: list[dict] | None = None,
    history: list[dict] | None = None,
) -> LLMResponse:
    """Produce an ``LLMResponse`` for a user message.

    In mock mode, parses the message deterministically. Otherwise assembles the
    prompt and calls Cerebras. Any failure degrades to a safe no-action response
    so the chat endpoint never surfaces a 500 from the LLM path.
    """
    if is_mock_enabled():
        # Imported lazily to avoid any import-time coupling.
        from .mock import mock_response

        return mock_response(user_message)

    try:
        messages = build_messages(user_message, portfolio_state, watchlist_context, history)
        return _call_cerebras(messages)
    except Exception:  # noqa: BLE001 — never let LLM issues 500 the request
        logger.exception("LLM completion failed; returning safe fallback response")
        return LLMResponse(message=_ERROR_FALLBACK)
