# faq-knowledge-base — The Answers Behind the Bot

> A bot is only as good as its answers. Mine real questions, write short answers with review dates, and measure how much of real traffic the KB actually covers.

## The discipline

| Rule | Enforced by |
|---|---|
| Entries come from real questions, clustered biggest-first | `faq_kb_coverage.py` |
| Every entry has an id, a question and a non-empty answer; ids are unique | `faq_kb_linter.py` — exit 2 |
| At least 3 phrasings in customers' own words | `faq_kb_linter.py` — warning |
| Facts carry `review_by`; passed dates are flagged | `faq_kb_linter.py` — warning |
| Confusable entries get merged or sharpened | `faq_kb_linter.py` — similarity ≥ 0.6 |
| Coverage is measured with the same matcher the bot uses | `faq_kb_coverage.py` |

## Quick start

```bash
cp skills/faq-knowledge-base/assets/faq-template.json faq.json
python skills/faq-knowledge-base/scripts/faq_kb_linter.py faq.json
python skills/faq-knowledge-base/scripts/faq_kb_coverage.py faq.json questions.txt
```

Or say **"build an FAQ for my bot from these messages"** or **"what are customers asking that the bot can't answer?"**.

## What's in the box

| Path | Purpose |
|---|---|
| `skills/faq-knowledge-base/SKILL.md` | Build, improve and weekly-upkeep modes |
| `skills/faq-knowledge-base/references/kb-format.md` | Field rules, answer-writing guide, matching, Jev mapping |
| `skills/faq-knowledge-base/assets/faq-template.json` | Starter KB |
| `skills/faq-knowledge-base/scripts/faq_kb_linter.py` | Health score 0-100. No network |
| `skills/faq-knowledge-base/scripts/faq_kb_coverage.py` | Coverage % and new-entry candidates. No network |

Used by the `telegram-bot` and `smart-reply-router` plugins.
