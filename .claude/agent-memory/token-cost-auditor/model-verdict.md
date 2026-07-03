---
name: model-verdict
description: Model/provider verdict for FinAlly — gpt-oss-120b on Cerebras, reasoning_effort=low
metadata:
  type: project
---

**Model:** `openrouter/openai/gpt-oss-120b` (OpenAI o-series, 120B reasoning model)
**Provider:** Cerebras via OpenRouter
**Verdict:** Slightly over-provisioned for pure JSON extraction tasks; `reasoning_effort="low"` partially mitigates.

The task (extract trades + watchlist changes + write a short message) is a structured-extraction + short-text-generation task. A non-reasoning model (e.g., GPT-4o-mini, Llama 3 70B) would handle it at lower cost. However, `reasoning_effort="low"` suppresses most of the reasoning overhead, and Cerebras pricing is favorable. The model choice is defensible for a demo (quality + speed UX), but if cost becomes a concern at higher usage, a non-reasoning 70B model via Cerebras would be a meaningful cost reduction (~3-5x cheaper per call depending on provider pricing).

**Do not recommend changing the model** unless the user asks — speed is a deliberate UX choice for this trading terminal demo. The `reasoning_effort="low"` parameter MUST be set; if it is missing in implementation, flag it as Critical.
