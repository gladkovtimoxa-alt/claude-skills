# KB format and answer-writing guide

The format is shared by three plugins: `telegram-bot` loads it with `--kb`, `smart-reply-router` uses entry ids as `faq_match` options, and `jev` question design turns entries into Choice criteria. Keep one file per business / bot.

## Fields

### `meta`

| Field | Required | Meaning |
|---|---|---|
| `name` | no | Human name of the KB |
| `language` | no | Main language code (`ru`, `en`) — answers should be in it |
| `greeting` | no | Bot reply to `/start` and `/help` |
| `fallback` | no | Bot reply when it can't answer and forwards the question |
| `updated` | no | Last time the file was reviewed as a whole |

### `entries[]`

| Field | Required | Rule |
|---|---|---|
| `id` | **yes** | Unique, lowercase, `a-z 0-9 _ -`, stable forever (it's referenced by logs, Jev options and routing policies). Prefix `faq_`. |
| `question` | **yes** | Canonical question in customer language. |
| `answer` | **yes** | What the bot sends. ≤ ~600 chars ideal, hard limit 4096 (one Telegram message). |
| `phrasings` | recommended | 3-8 real variants from messages. The matcher and Jev learn more from these than from `question`. |
| `intent` | recommended | Matches smart-reply-router intents (`pricing`, `how_to`, …). |
| `owner` | recommended | Who confirms the facts. |
| `updated` | recommended | `YYYY-MM-DD` of last confirmation. |
| `review_by` | recommended for facts | `YYYY-MM-DD`; the linter warns once it passes. |

Unknown extra fields are ignored by all tools — fine for your own notes (`notes`, `source_url`).

## Writing answers

1. **Answer first.** "990 ₽/month. Pro is 2 490 ₽." — not "Thank you for your question! Our pricing…".
2. **One follow-up detail.** Anticipate the next question in one sentence (payment methods after prices, spam folder after password reset).
3. **No promises you can't keep.** Avoid "always", "guaranteed", exact delivery dates unless they are policy.
4. **Link when details are long.** One sentence + a link beats a wall of text.
5. **Same language and tone as the customers.**
6. **Nothing private.** The KB is effectively public — anyone can ask the bot.

## Phrasings that work

- Copy them from real messages; keep short ones ("цена", "прайс") — people type two words.
- Include the other language if customers mix (`"how much"` next to `"сколько стоит"`).
- Don't reuse the same phrasing in two entries — the linter flags confusable pairs at similarity ≥ 0.6.

## How matching works (so you can predict it)

`faq_bot.py`, `faq_kb_linter.py` and `faq_kb_coverage.py` share one deterministic matcher:

1. Lowercase, split into words, drop common stopwords (ru + en), keep the first 5 characters of each word (a crude stem: "пароль"/"пароля" → "парол").
2. Score = Dice similarity between the question's words and each of the entry's `question` + `phrasings`; the best variant counts. 0-100.
3. Answer when the top score ≥ 50 **and** leads the runner-up by ≥ 10. Otherwise forward.

It's fast, free and predictable, and weak on synonyms. When phrasing varies a lot, switch the matcher to Jev (see `engineering/jev` and the telegram-bot reference) — the KB stays the same.

## Entries as Jev Choice options

```python
criteria = {
    e["id"]: {"what": e["question"], "examples": e.get("phrasings", [])[:3]}
    for e in kb["entries"]
}
criteria["no_match"] = {"what": "no entry answers the question completely"}
```

Up to 255 entries per Choice. Larger KBs: route by `intent` first, then match within the intent.
