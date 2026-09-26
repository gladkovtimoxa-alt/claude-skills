# telegram-bot — Answers What It Knows, Hands You the Rest

> A Telegram bot on the official Bot API. Known questions: instant answer from your knowledge base, zero AI tokens. Unknown: forwarded to you — reply to it and the bot delivers your answer.

## The discipline

| Rule | Enforced by |
|---|---|
| Token and owner id only from env (`TELEGRAM_BOT_TOKEN`, `TELEGRAM_OWNER_CHAT_ID`) | `faq_bot.py` |
| Answer only above a match score and a lead over the runner-up; otherwise relay | `faq_bot.py` — `--min-score`, `--min-margin` |
| Owner replies reach the original person as a reply to their message | `faq_bot.py` relay map |
| Offset, relay map and unanswered log survive restarts | `faq_bot.py` state file |
| Honour `retry_after` on 429; split messages over 4096 chars | `faq_bot.py` |
| LLM text never goes to a client without the owner | `SKILL.md`, `references/bot-api-essentials.md` |

## Quick start

```bash
python skills/telegram-bot/scripts/faq_bot.py --sample                  # offline demo
python skills/telegram-bot/scripts/faq_bot.py --ask "сколько стоит" --kb faq.json
TELEGRAM_BOT_TOKEN=... python skills/telegram-bot/scripts/faq_bot.py --run --kb faq.json
```

## What's in the box

| Path | Purpose |
|---|---|
| `skills/telegram-bot/SKILL.md` | Launch, grow-the-KB, and add-AI modes; trust rules |
| `skills/telegram-bot/references/bot-api-essentials.md` | BotFather, methods, limits, formatting, groups, webhook, systemd/Docker, Jev/LLM extension |
| `skills/telegram-bot/scripts/faq_bot.py` | The bot: long polling, KB answers, owner relay. Offline `--ask` / `--sample` modes |

The KB format comes from the `faq-knowledge-base` plugin.
