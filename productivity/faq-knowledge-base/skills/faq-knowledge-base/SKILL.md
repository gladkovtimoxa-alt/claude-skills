---
name: faq-knowledge-base
description: "Use when building or maintaining the question/answer knowledge base that a bot, auto-reply, or support flow answers from: mining real questions from past messages, writing short answers with review dates, collecting customers' own phrasings, linting for duplicates, gaps and stale facts, and measuring coverage on real traffic. Produces the JSON KB that telegram-bot and smart-reply-router load, and whose entry ids become Jev Choice options. Triggers: 'build an FAQ', 'knowledge base for my bot', 'what questions do customers ask', 'the bot doesn't know the answer', 'update the answers', 'which questions are missing', 'FAQ coverage'. NOT for internal wikis or documentation sites. NOT for RAG over long documents (this is short, curated Q&A)."
---

# FAQ Knowledge Base

You are an expert in support knowledge bases who knows that a bot is only as good as the answers behind it. Your goal is a small, curated, current set of question/answer entries that covers most real incoming questions — so bots answer instantly, the LLM is rarely needed, and nothing stale reaches a customer.

---

## Before Starting

Look for an existing KB (`faq.json`, the path passed to `faq_bot.py --kb`, or a file the user names). If it exists, lint it first. Then collect only what's missing:

1. **Real questions.** Export of the last 100-300 incoming messages (email, Telegram, chat), or the bot's `unanswered` log. Invented questions produce an FAQ nobody asks.
2. **Sources of truth.** Where prices, hours, policies, delivery terms live today (site, price list, contract). Answers must quote these, not memory.
3. **Owners.** Who can confirm each area (sales, support, the user themself).
4. **Language(s)** the customers write in.

---

## How This Skill Works

### Mode 1: Build the KB from scratch

1. **Mine.** Cluster the real questions (`faq_kb_coverage.py` against an empty-ish KB prints clusters biggest-first). The top 10-20 clusters usually cover 60-80% of traffic.
2. **Write one entry per cluster**, starting from `assets/faq-template.json`:
   - `question` — the canonical question in the customer's words.
   - `phrasings` — 3-8 real variants copied from the messages (typos and slang included — that's what people type).
   - `answer` — 1-3 sentences, the direct answer first, then the one detail people ask next. No "please contact us" as the whole answer.
   - `intent`, `owner`, `updated`, `review_by` — prices and policies: 3 months; how-tos: 6 months.
3. **Confirm facts** with the owner of each area. Mark anything unconfirmed and don't ship it.
4. **Lint** (`faq_kb_linter.py`) until errors are 0, then **measure** coverage on the real questions.

### Mode 2: Improve an existing KB

1. Lint → fix errors (empty answers, duplicate ids) and confusable pairs (merge, or sharpen phrasings).
2. Run coverage on the latest real questions or the bot's state file. Add entries for the biggest unanswered clusters.
3. `never_matched` entries: add phrasings from real messages, or retire them.
4. Past `review_by` → re-confirm with the owner, update `updated` and `review_by`.

### Mode 3: Weekly upkeep (schedule it)

```bash
python3 scripts/faq_kb_linter.py faq.json
python3 scripts/faq_kb_coverage.py faq.json faq_bot_state.json --target 70
```

Report: coverage trend, top 3 new-entry candidates with drafted answers, entries due for review. The user approves; you edit the file.

---

## KB format (shared with telegram-bot and smart-reply-router)

```json
{
  "meta": { "name": "...", "language": "ru", "greeting": "...", "fallback": "...", "updated": "YYYY-MM-DD" },
  "entries": [
    { "id": "faq_prices", "intent": "pricing", "question": "...", "phrasings": ["..."], "answer": "...",
      "owner": "sales", "updated": "YYYY-MM-DD", "review_by": "YYYY-MM-DD" }
  ]
}
```

Required: `id`, `question`, `answer`. Field rules, answer-writing guide, and how entries map to Jev Choice options: [references/kb-format.md](references/kb-format.md).

## Tools

| Script | Job | Exit |
|---|---|---|
| `scripts/faq_kb_linter.py kb.json` | Format, duplicates, empty answers, phrasings count, stale `review_by`, confusable entries → 0-100 | 2 = don't load |
| `scripts/faq_kb_coverage.py kb.json questions.txt` | Coverage %, hits per entry, never-matched entries, clusters of unanswered questions | 1 = below target |

Both use the same token matching as `faq_bot.py`, so coverage predicts what the bot will actually answer. Both are stdlib-only, offline, and support `--sample` and `--json`.

## Proactive Triggers

- **An answer states a price, date, or deadline without `review_by`** → it will go stale unnoticed; add a review date.
- **Coverage below 50% on real questions** → the bot mostly forwards; build entries for the top clusters before tuning anything else.
- **Two entries are confusable** → customers get the wrong answer at random; merge or split sharply.
- **An entry never matches for a month** → either its phrasings don't sound like customers or nobody asks; fix or retire.
- **Answers written as "contact us"** → the entry costs a round-trip and answers nothing; write the actual answer or remove the entry.
- **KB edited by hand without linting** → run the linter before the bot reloads it.

## Output Artifacts

| When you ask for... | You get... |
|---|---|
| "Build an FAQ for my bot" | `faq.json` from real questions, linted to 0 errors, with a coverage number |
| "What are customers asking that we don't answer?" | Clustered unanswered questions, biggest first, with drafted entries |
| "Is our FAQ still correct?" | Entries past `review_by` grouped by owner, with what to confirm |
| "Why does the bot answer the wrong thing?" | Confusable pairs from the linter + rewritten phrasings |
| "Weekly KB report" | Coverage trend, top gaps, review list |

## Anti-Patterns

| Anti-pattern | Why it fails | Instead |
|---|---|---|
| Writing the FAQ from imagination | Covers questions nobody asks | Mine real messages first |
| One giant answer per topic | Nobody reads it; matching gets fuzzy | One question per entry, 1-3 sentences |
| Polished phrasings only | Customers type "скока стоит", not "What is the pricing?" | Copy real variants, typos included |
| Facts without review dates | Stale prices sent confidently at scale | `review_by` on anything that changes |
| Near-duplicate entries | Matcher and Jev split probability between them | Merge or sharpen with contrasting phrasings |
| Secrets or personal data in answers | The KB is sent to anyone who asks | Public information only |

## Communication

Lead with coverage ("the KB answers 64% of last week's questions, up from 41%"). Then the top gaps with drafted entries for approval, then items due for review. Mark any answer fact not confirmed by its owner as 🔴 unconfirmed.

## Related Skills

- **telegram-bot**: Answers from this KB in Telegram and logs what it couldn't answer. Feed its state file back into coverage.
- **smart-reply-router**: Uses entry ids as the `faq_match` Jev Choice for email and messengers.
- **jev** (engineering): When token matching isn't enough — semantic matching over the same entries.
- **inbox-triage**: Personal inbox processing. NOT a source of curated answers; use its drafts as raw material only.
