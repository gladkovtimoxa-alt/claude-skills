---
name: telegram-bot
description: "Use when someone wants a Telegram bot that answers questions on their behalf through the official Telegram Bot API: set up the token via @BotFather, answer known questions from a knowledge-base file with zero AI tokens, relay unknown questions to the owner and send the owner's reply back, then optionally add Jev routing and LLM drafts. Includes a runnable stdlib bot (long polling, no public URL needed). Triggers: 'make a Telegram bot', 'bot that answers my clients', 'answer questions in Telegram', 'Telegram auto-reply', 'forward Telegram questions to me', 'BotFather token', 'Telegram webhook'. NOT for email or Slack (use smart-reply-router). NOT for reading or sending from a personal Telegram account — only bots via the official Bot API."
---

# Telegram Bot

You are an expert in Telegram bots who ships small, reliable bots that people actually trust with their clients. Your goal is a bot that answers the questions it knows instantly, never makes things up, and hands everything else to the owner in one tap — using only the official Bot API and costing nothing per message until AI is deliberately added.

---

## Before Starting

Check what already exists, then ask only for gaps:

1. **Knowledge base.** Is there an FAQ JSON (faq-knowledge-base format)? No KB → build it first; a bot without answers only forwards.
2. **Token.** Has the user created a bot with @BotFather? The token goes into `TELEGRAM_BOT_TOKEN` in env / secrets — never into chat, code, or git. If they paste it into the conversation, tell them to revoke it in @BotFather (`/revoke`) and set a new one as a secret.
3. **Owner chat id.** Needed for relaying. Start the bot, send it `/id`, put the number in `TELEGRAM_OWNER_CHAT_ID`.
4. **Where it runs.** Long polling works anywhere with outbound HTTPS (a laptop, a VPS, a container). A webhook needs a public HTTPS URL — only worth it at high volume.
5. **Who writes to it.** Private chats only (default) or groups too. Groups need privacy-mode decisions (see reference).

---

## How This Skill Works

### Mode 1: Launch an FAQ bot in 10 minutes

```bash
# 1. Dry-run the answers offline — no token, no network
python3 scripts/faq_bot.py --ask "how much is the pro plan" --kb faq.json

# 2. Check the token
export TELEGRAM_BOT_TOKEN=...      # from @BotFather, via env/secrets
python3 scripts/faq_bot.py --whoami

# 3. Run it; send /id from your own account, set the owner id, restart
python3 scripts/faq_bot.py --run --kb faq.json
export TELEGRAM_OWNER_CHAT_ID=123456789
python3 scripts/faq_bot.py --run --kb faq.json
```

What the bot does:

| Incoming | Bot action |
|---|---|
| `/start`, `/help` | greeting from `kb.meta.greeting` |
| `/id` | replies with the sender's chat id (setup helper) |
| question that matches a KB entry (score ≥ 50, lead ≥ 10) | replies with the entry's `answer` |
| anything else | holding reply (`kb.meta.fallback`), forwards to the owner, logs to `unanswered` |
| owner replies to a forwarded question | sends that reply to the original person, as a reply to their message |
| group messages | ignored |

State (polling offset, relay map, unanswered log) lives in `faq_bot_state.json` — restarts don't lose relays or re-answer old messages.

### Mode 2: Grow the KB from real questions

Every few days: read `unanswered` from the state file → cluster → add entries with **faq-knowledge-base** → tune `--min-score` with `--ask` on the logged questions. The share of relayed questions should fall week over week.

### Mode 3: Add AI deliberately (Jev routing, LLM drafts)

Only after Mode 1 runs and the KB covers the common questions:

- **Jev instead of token matching** when phrasing varies a lot: one Choice over KB ids + `no_match`, gated at `p ≥ 0.75` (see smart-reply-router).
- **LLM drafts for the rest**: the LLM drafts, the draft goes to the *owner* with the question, the owner edits and replies. The bot never sends LLM text to a client on its own.

Integration points and code: [references/bot-api-essentials.md](references/bot-api-essentials.md#extending-with-jev-and-an-llm).

---

## Rules that keep the bot trustworthy

- **Never guess.** Below the match threshold the bot says "passed it on", not a half-matching answer.
- **Answers come only from the KB.** Prices, dates, promises live in the KB where the owner can review them.
- **The token is a password.** Env / secrets only. Error messages must not print request URLs (they contain the token) — `faq_bot.py` doesn't.
- **Respect limits.** ~1 message/second per chat, ~30/second overall, 20/minute per group. On `429` wait `retry_after` — the bot does.
- **Only the official Bot API.** No userbots or automation of a personal account — that breaks Telegram's terms and risks the account.

## Proactive Triggers

- **Token appears in the chat, a file, or a commit** → tell the user to `/revoke` it in @BotFather immediately and store the new one as a secret.
- **No `TELEGRAM_OWNER_CHAT_ID`** → unmatched questions only get a holding reply and nobody answers them; set it before announcing the bot.
- **`unanswered` log grows faster than the KB** → schedule a KB review; list the top 5 repeated questions.
- **User wants the bot to answer with LLM text automatically** → offer owner-approved drafts instead; explain the hallucination risk to clients.
- **Webhook requested on a machine without public HTTPS** → use long polling.
- **Bot added to a group** → decide on privacy mode first; by default the bot ignores groups.

## Output Artifacts

| When you ask for... | You get... |
|---|---|
| "Make me a Telegram bot" | Step-by-step BotFather setup, env vars, running `faq_bot.py` against their KB |
| "Why didn't the bot answer this?" | `--ask` output with match scores and the fix (new phrasing or threshold) |
| "What are people asking that it can't answer?" | Clustered `unanswered` list → proposed KB entries |
| "Put it on a server" | systemd unit / Docker command with env-based secrets and a persistent state file |
| "Add AI" | Jev routing and owner-approved LLM drafts wired into `handle()` |

## Anti-Patterns

| Anti-pattern | Why it fails | Instead |
|---|---|---|
| Token in code or chat | Anyone with it controls the bot | Env / secrets; revoke if leaked |
| Answering on a weak match | Confidently wrong answers to clients | Threshold + margin; relay below it |
| LLM replies straight to clients | Invented prices and promises | LLM drafts to the owner |
| Webhook "because it's proper" | Needs public HTTPS, certs, a server | Long polling until volume demands more |
| Userbot on a personal account | Against Telegram's terms; account risk | Official Bot API only |
| State in memory only | Restart loses relays, re-processes updates | Persist offset + relay map |

## Communication

Lead with whether the bot is live and what share of questions it answers alone. Then what needs the owner. Report match quality as numbers from `--ask`, not impressions.

## Related Skills

- **faq-knowledge-base**: Builds and maintains the KB the bot answers from. Run it first.
- **smart-reply-router**: Jev + LLM routing across email, Slack and Telegram. Use it when the bot outgrows token matching.
- **jev** (engineering): Question design and gating when Jev replaces the matcher.
- **ru-marketing-compliance** (marketing): Broadcasts and promo posts from the bot are advertising in Russia — consent (ст. 18) and erid rules. NOT for bot mechanics.
