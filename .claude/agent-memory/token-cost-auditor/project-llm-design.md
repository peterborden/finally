---
name: project-llm-design
description: FinAlly LLM integration design decisions — model, provider, history window, structured outputs
metadata:
  type: project
---

Model: `openrouter/openai/gpt-oss-120b` via OpenRouter with Cerebras inference provider.
Skill: cerebras (at `.claude/skills/cerebras/SKILL.md`).
Call params: `reasoning_effort="low"`, `extra_body={"provider": {"order": ["cerebras"]}}`.
Structured output: Pydantic model via `response_format=MyBaseModelSubclass`.
History window: last 20 messages (10 turns) from `chat_messages` table — explicit cap, deliberate.
No streaming: full response returned (Cerebras fast enough that loading indicator suffices).
Retry policy: 1 retry on parse/validation failure, then degrade to plain message with no actions.
Mock mode: `LLM_MOCK=true` returns deterministic canned responses — no API calls.

**Why:** Course capstone demo; Cerebras chosen for speed (low latency trading terminal feel). reasoning_effort=low reduces cost on a reasoning-capable model.
**How to apply:** Do not recommend switching the provider or model without strong justification — speed is a deliberate UX goal. Do flag if reasoning_effort=low is not being set.
