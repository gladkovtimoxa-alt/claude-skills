# Routing policy

`reply_route_planner.py` reads a policy JSON. Every field is optional; defaults are shown.

```json
{
  "mode": "draft",
  "red_line_intents": ["refund", "legal", "complaint", "personal"],
  "auto_send_intents": [],
  "thresholds": {
    "spam": 0.9,
    "needs_human": 0.6,
    "intent_min_p": 0.55,
    "faq_min_p": 0.75,
    "faq_min_presence": 0.8,
    "critical_urgency": 1.5
  }
}
```

| Field | Meaning |
|---|---|
| `mode` | `draft` — nothing is sent, everything becomes a draft. `auto` — FAQ templates for `auto_send_intents` may be sent. |
| `red_line_intents` | Intents that always go to the human, whatever the other answers say. |
| `auto_send_intents` | Whitelist for sending FAQ templates in `auto` mode. Red-line intents are removed from it even if listed. |
| `spam` | `is_spam ≥` this → `ignore`. |
| `needs_human` | `needs_human ≥` this → `human`. |
| `intent_min_p` | If the intent's top probability is lower, the intent is treated as uncertain and the message is never auto-sent. |
| `faq_min_p` | `faq_match` top probability needed to answer with a template. |
| `faq_min_presence` | `1 − p(no_match)` needed on `faq_match`. |
| `critical_urgency` | Score at or above this (0-based level index, e.g. 1.5 = between Urgent and Critical on a 3-level scale) → `human`. |

## Rule order

1. `is_spam ≥ spam` → **ignore**
2. intent is a red line (top pick, or any red-line intent with p ≥ 0.3) → **human**
3. `needs_human ≥ needs_human` → **human**
4. `urgency.score ≥ critical_urgency` → **human**
5. FAQ gate passes (`faq_min_p` and `faq_min_presence`, top is not `no_match`) → **faq_template**; `send = true` only if `mode = auto`, intent in the whitelist, and `intent_min_p` passed
6. otherwise → **llm_draft** (never sent automatically)

The "any red-line intent with p ≥ 0.3" check is deliberate: when a message is 60% `pricing` and 35% `refund`, it's safer to show it to the human than to auto-answer the pricing half.

## Why these defaults

- `faq_min_p` 0.75 is higher than the generic reversible gate (0.55) because a wrong template is visible to a customer, not just an internal tag.
- LLM drafts are never auto-sent: the LLM can invent prices, dates, and promises. A human skims the draft; that costs seconds.
- Red lines win over everything because the cost of a wrong refund or legal answer is asymmetric.
