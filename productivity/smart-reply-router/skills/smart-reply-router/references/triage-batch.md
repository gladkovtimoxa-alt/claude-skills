# Triage batch — one Jev request per message

Copy, then replace the intents and FAQ ids with the user's own. All five questions run in parallel in one call. API details: `engineering/jev/skills/jev/references/api-reference.md`.

```json
{
  "model": "jev-latest",
  "state": {
    "message": {
      "channel": "email",
      "from": "customer@example.com",
      "subject": "Order 1182",
      "text": "Hi, I paid twice for order 1182. Can you refund one payment?"
    }
  },
  "questions": {
    "intent": {
      "type": "choice",
      "instructions": "What does the sender of `message.text` want?",
      "criteria": {
        "pricing":   { "what": "asks what something costs, plans, discounts", "not_for": "already paid, wants money back", "examples": ["how much is the pro plan"] },
        "how_to":    { "what": "asks how to do something with the product", "not_for": "reports that something is broken" },
        "bug":       { "what": "something doesn't work, error, crash", "not_for": "question about how to use it" },
        "refund":    { "what": "wants money back, double charge, cancel and refund", "not_for": "price question before buying", "examples": ["charged twice", "refund please"] },
        "scheduling":{ "what": "wants to book, move, or cancel a meeting or call" },
        "no_match":  { "what": "anything else, personal messages, unclear" }
      }
    },
    "faq_match": {
      "type": "choice",
      "instructions": "Which knowledge-base entry fully answers `message.text`? Choose no_match if none answers it completely.",
      "criteria": {
        "faq_prices":   { "what": "Current plans and prices", "examples": ["how much", "price list"] },
        "faq_reset_pw": { "what": "How to reset a password", "examples": ["can't log in", "forgot password"] },
        "faq_hours":    { "what": "Working hours and response times" },
        "no_match":     { "what": "no entry answers the whole question" }
      }
    },
    "urgency": {
      "type": "score",
      "instructions": "How urgent is `message.text` for the sender?",
      "criteria": [
        { "what": "Normal",   "signals": ["question, no deadline"] },
        { "what": "Urgent",   "signals": ["blocks their work", "needs an answer today"] },
        { "what": "Critical", "signals": ["work fully stopped", "money or data at risk", "threatens to leave or complain publicly"] }
      ]
    },
    "is_spam": {
      "type": "noul",
      "instructions": "Is `message.text` spam, advertising, or an automated notification that needs no reply?",
      "criteria": { "true": "promotion, cold sales pitch, newsletter, no-reply notification", "false": "a person asking or telling something that expects an answer" }
    },
    "needs_human": {
      "type": "noul",
      "instructions": "Does answering `message.text` require a decision or personal judgement from the owner?",
      "criteria": { "true": "money decisions, exceptions to rules, conflicts, legal, personal relationships", "false": "information that is already documented" }
    }
  }
}
```

## Building the FAQ Choice

- One option per KB entry, key = the entry id from the FAQ file, `what` = the question it answers, `examples` = 1-3 real phrasings from the KB's `phrasings` list.
- Up to 255 entries per Choice. Beyond that, first route by intent, then ask `faq_match` only over that intent's entries.
- Always keep `no_match`. Its share across a day is the best signal of what the KB is missing.

## Feeding the planner

Save one object per message into a list and run `reply_route_planner.py` on it:

```json
[
  {
    "id": "msg-1",
    "channel": "email",
    "answers": { "intent": { }, "faq_match": { }, "urgency": { }, "is_spam": 0.02, "needs_human": 0.81 }
  }
]
```

`answers` is exactly the `answers` object Jev returned for that message.
