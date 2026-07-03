---
name: prompt-construction-risks
description: Token waste risks in FinAlly /api/chat prompt construction — portfolio context, watchlist prices, history window
metadata:
  type: project
---

Flagged during initial design/spec audit (pre-implementation):

1. **Portfolio context is fully re-injected every call** — cash, all positions with P&L, all watchlist tickers with live prices, total value. With 10 watchlist tickers + positions this is ~200–400 tokens per call, fully variable. The spec does not require this to include per-ticker live prices in the watchlist section; only positions need current price for P&L context.

2. **Watchlist prices inflate context unnecessarily** — the watchlist section (§9 step 1) includes "watchlist with live prices." For 10+ tickers this adds redundant price data the LLM rarely needs to act on watchlist items. The positions already carry current price + P&L; the watchlist could be reduced to ticker symbols only.

3. **No system prompt caching specified** — the system prompt (persona + instructions) is static and should be Anthropic/OpenRouter prompt-cached, but the spec doesn't call this out. For OpenRouter/Cerebras this may or may not be supported — worth verifying at implementation time.

4. **History window: 20 messages is reasonable** — deliberate cap, not a waste pattern. Do not flag.

5. **Retry sends same full payload** — the single retry on parse failure re-sends the identical prompt. Since the failure is typically a model formatting error, not a prompt error, this is acceptable and bounded (max 1 retry).

**How to apply:** When reviewing the actual prompt-construction implementation, check whether watchlist prices are included and whether the portfolio context is slimmed to only what the LLM needs for reasoning (positions with P&L + cash + total value). Flag watchlist ticker prices as redundant unless the LLM is explicitly using them.
