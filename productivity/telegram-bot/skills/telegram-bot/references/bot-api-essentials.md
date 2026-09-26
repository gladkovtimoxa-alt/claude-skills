# Telegram Bot API essentials

Official documentation: https://core.telegram.org/bots/api (methods, types) and https://core.telegram.org/bots/features (BotFather, privacy mode, commands).

## Setup with @BotFather

1. Open @BotFather → `/newbot` → name → username ending in `bot`.
2. Copy the token **straight into a secret / env var** `TELEGRAM_BOT_TOKEN`. Don't paste it into chats.
3. Optional: `/setdescription`, `/setabouttext`, `/setuserpic`, `/setcommands` (e.g. `start - Start`, `help - What I can do`).
4. Leaked token → `/revoke` in @BotFather, set the new one.

## Methods the bot uses

All calls: `POST https://api.telegram.org/bot<TOKEN>/<method>` with a JSON body. Every response is `{"ok": true, "result": ...}` or `{"ok": false, "error_code": N, "description": "...", "parameters": {"retry_after": S}}`.

| Method | Use | Key params |
|---|---|---|
| `getMe` | Check the token | — |
| `getUpdates` | Long polling | `offset` (last `update_id` + 1), `timeout` (seconds to hold the connection), `allowed_updates` |
| `sendMessage` | Reply | `chat_id`, `text` (≤ 4096 chars), `reply_parameters: {message_id}`, optional `parse_mode` |
| `setWebhook` / `deleteWebhook` | Switch to / from webhooks | `url`, `secret_token` |
| `answerCallbackQuery` | Acknowledge inline-button taps | `callback_query_id` |

`getUpdates` and a webhook are mutually exclusive: if a webhook is set, polling returns 409. `deleteWebhook` first.

## Update shape (the parts that matter)

```json
{
  "update_id": 912345678,
  "message": {
    "message_id": 55,
    "date": 1790000000,
    "chat": { "id": 123456789, "type": "private" },
    "from": { "id": 123456789, "first_name": "Ann", "username": "ann" },
    "text": "How much is the pro plan?",
    "reply_to_message": { "message_id": 54 }
  }
}
```

`chat.type` is `private`, `group`, `supergroup`, or `channel`. Always confirm the update by moving `offset` past it, or Telegram redelivers it.

## Limits

| Limit | Value |
|---|---|
| Messages to one chat | ~1 per second |
| Messages overall | ~30 per second |
| Messages to one group | 20 per minute |
| Message length | 4096 characters (split longer ones) |

On `429` read `parameters.retry_after` and sleep that long.

## Formatting

Plain text is safest. With `parse_mode: "MarkdownV2"` these characters must be escaped with `\`: `_ * [ ] ( ) ~ ` > # + - = | { } . !`. A single unescaped `.` makes the whole send fail with 400. `HTML` mode needs only `<`, `>`, `&` escaped.

## Groups and privacy mode

By default a bot in a group only sees commands and replies to its own messages (privacy mode on). To answer free-text questions in a group, turn privacy mode off in @BotFather (`/setprivacy`) — then it sees every message, so be explicit with the group about it. `faq_bot.py` ignores groups entirely; extend `handle()` if needed.

## Webhook (only when polling isn't enough)

```bash
curl -sS "https://api.telegram.org/bot$TELEGRAM_BOT_TOKEN/setWebhook" \
  -d url=https://bot.example.com/telegram \
  -d secret_token="$TELEGRAM_WEBHOOK_SECRET"
```

Requirements: public HTTPS on port 443, 80, 88 or 8443; check the `X-Telegram-Bot-Api-Secret-Token` header on every request and reject mismatches; answer `200` fast and do the work asynchronously.

## Running it for real

**systemd (VPS)**

```ini
# /etc/systemd/system/faq-bot.service
[Unit]
Description=Telegram FAQ bot
After=network-online.target

[Service]
WorkingDirectory=/opt/faq-bot
EnvironmentFile=/etc/faq-bot.env
ExecStart=/usr/bin/python3 faq_bot.py --run --kb faq.json --state /var/lib/faq-bot/state.json
Restart=always
RestartSec=5
User=faqbot

[Install]
WantedBy=multi-user.target
```

`/etc/faq-bot.env` holds `TELEGRAM_BOT_TOKEN=...` and `TELEGRAM_OWNER_CHAT_ID=...`, mode `600`, owned by root.

**Docker**

```bash
docker run -d --restart=always --name faq-bot \
  --env-file ./faq-bot.env \
  -v "$PWD":/app -w /app python:3.12-slim \
  python faq_bot.py --run --kb faq.json --state /app/state/state.json
```

## Extending with Jev and an LLM

`faq_bot.py` is deliberately AI-free. Add AI in `handle()`, at the point where `match()` returns `answered: false`:

```python
result = match(kb, text, args.min_score, args.min_margin)
if not result["answered"] and os.environ.get("JEV_API_KEY"):
    # One Jev Choice over KB ids + no_match (see engineering/jev).
    jev = jev_ask({"question": {"text": text}}, {"faq": {
        "type": "choice",
        "instructions": "Which entry fully answers `question.text`? no_match if none does.",
        "criteria": {e["id"]: {"what": e["question"], "examples": e.get("phrasings", [])[:3]} for e in kb["entries"]}
                    | {"no_match": {"what": "no entry answers it completely"}},
    }})
    faq = jev["answers"]["faq"]
    top = faq["choice"]
    if top != "no_match" and faq["probabilities"][top] >= 0.75:
        result = {**result, "answered": True, "entry_id": top,
                  "answer": next(e["answer"] for e in kb["entries"] if e["id"] == top)}
```

For an LLM draft, generate it only for questions that are still unanswered, and **send the draft to the owner** together with the forwarded question ("Draft: … — reply to send your own version"). The owner's reply is what reaches the client, through the existing relay. Keep `max_tokens` capped and give the LLM only the question plus the top 3 KB entries.
