# Designing Jev questions

How to phrase questions so the right answer gets a high probability. Everything here comes from measured runs in the reference experiments (https://github.com/gmoreva/jev-scripts) plus the official guide https://docs.typesafe.ai/primitives/advanced.md.

## 1. Choice

**Contrast beats labels.** Give each option what it covers, what it does *not* cover, and one or two real examples in the user's own words.

```json
{
  "type": "choice",
  "instructions": "Which team should handle `ticket.text`?",
  "criteria": {
    "billing":   { "what": "payments, invoices, refunds, charges", "not_for": "where is my parcel", "examples": ["charged twice", "refund please"] },
    "delivery":  { "what": "shipping status, lost or late parcels", "not_for": "refunds", "examples": ["parcel hasn't arrived"] },
    "account":   { "what": "login, password, profile, 2FA", "not_for": "payment cards" },
    "no_match":  { "what": "anything else, spam, empty or unclear message" }
  }
}
```

Rules:

- Always add `no_match` (or `none`) when "nothing fits" is a valid outcome. Use `1 − p(no_match)` as "is the answer even here?".
- Up to 255 options. With many options (UI elements) expect lower `confidence` — gate on `p(top)` instead.
- Picking a UI element: options are element refs (`e12`, `e57`), criteria are their visible text + role + position. Prioritise in-viewport elements, de-duplicate by text, cap around 150 candidates.
- Near-duplicate options honestly split probability. Let code merge them (sum p) and pick the most actionable node.

## 2. Noul

A single probability of "yes". No confidence field. 0.5 means "I don't know", not "somewhat".

```json
{
  "type": "noul",
  "instructions": "Does `page` show that the search task is complete?",
  "criteria": {
    "true":  "results list is visible AND filters `price_max` and `breakfast` are applied AND at least one card matches",
    "false": "search form still open, filters missing, or no matching cards"
  }
}
```

Rules:

- **Evidence in state.** "Task done?" with applied filters and per-card flags in `state` → 0.93+. Without them → ~0.3. Extract the facts in code first, then ask.
- Multi-label = one Noul per label, all in the same batch.
- Typical thresholds: `≥ 0.9` act, `≤ 0.1` act as "no", `0.4-0.6` escalate.

## 3. Score

Ordered levels, 2 to 10, each described as a situation with signals — never as a bare number.

```json
{
  "type": "score",
  "instructions": "How urgent is `ticket.text` for the customer?",
  "criteria": [
    { "what": "Normal",   "signals": ["question or request, work not blocked"] },
    { "what": "Urgent",   "signals": ["blocks part of their work", "needs an answer today"] },
    { "what": "Critical", "signals": ["work fully stopped", "money or data at risk", "legal threat"] }
  ]
}
```

The answer can land between levels (1.4 = between Urgent and Critical). For ranking N items, ask one Score per item on the same axis in one batch, then sort.

## 4. State

- Named fields, only what questions reference: `{"ticket": {...}, "customer": {"plan": "pro"}}`.
- Reference nested values in instructions with backticks.
- Pre-compute facts in code (dates, totals, flags). Jev judges meaning; it shouldn't do arithmetic.
- Keep PII out unless a question needs it.

## 5. Batching a step

Put every question you need at one step into one request:

```json
{
  "model": "jev-latest",
  "state": { "message": { "text": "..." } },
  "questions": {
    "intent":   { "type": "choice", "instructions": "...", "criteria": { } },
    "urgency":  { "type": "score",  "instructions": "...", "criteria": [ ] },
    "is_spam":  { "type": "noul",   "instructions": "...", "criteria": { } },
    "needs_human": { "type": "noul", "instructions": "...", "criteria": { } }
  }
}
```

One request with 13 questions ≈ 12× cheaper and 10× faster than 13 requests. Questions can't see each other's answers — if one depends on another, split into two steps.

## 6. When NOT to use Jev

- The output is free text (reply, summary, code) → LLM.
- The options aren't known in advance and can't be enumerated → LLM.
- Multi-step reasoning or planning in an unfamiliar situation → LLM, then come back to Jev for the next routine decision.
