# Основы Telegram Bot API

Официальная документация: https://core.telegram.org/bots/api (методы, типы) и https://core.telegram.org/bots/features (BotFather, режим приватности, команды).

## Настройка через @BotFather

1. Откройте @BotFather → `/newbot` → имя → username, оканчивающийся на `bot`.
2. Скопируйте токен **сразу в секрет / переменную окружения** `TELEGRAM_BOT_TOKEN`. Не вставляйте его в чаты.
3. По желанию: `/setdescription`, `/setabouttext`, `/setuserpic`, `/setcommands` (например, `start - Начать`, `help - Что я умею`).
4. Токен утёк → `/revoke` в @BotFather и задайте новый.

## Методы, которые использует бот

Все вызовы: `POST https://api.telegram.org/bot<TOKEN>/<method>` с JSON-телом. Каждый ответ — `{"ok": true, "result": ...}` или `{"ok": false, "error_code": N, "description": "...", "parameters": {"retry_after": S}}`.

| Метод | Для чего | Ключевые параметры |
|---|---|---|
| `getMe` | Проверить токен | — |
| `getUpdates` | Long polling | `offset` (последний `update_id` + 1), `timeout` (сколько секунд держать соединение), `allowed_updates` |
| `sendMessage` | Ответ | `chat_id`, `text` (≤ 4096 символов), `reply_parameters: {message_id}`, необязательный `parse_mode` |
| `setWebhook` / `deleteWebhook` | Переключиться на вебхук / обратно | `url`, `secret_token` |
| `answerCallbackQuery` | Подтвердить нажатие inline-кнопки | `callback_query_id` |

`getUpdates` и вебхук взаимоисключающие: если вебхук установлен, опрос вернёт 409. Сначала `deleteWebhook`.

## Структура обновления (важные части)

```json
{
  "update_id": 912345678,
  "message": {
    "message_id": 55,
    "date": 1790000000,
    "chat": { "id": 123456789, "type": "private" },
    "from": { "id": 123456789, "first_name": "Анна", "username": "anna" },
    "text": "Сколько стоит тариф Pro?",
    "reply_to_message": { "message_id": 54 }
  }
}
```

`chat.type` — `private`, `group`, `supergroup` или `channel`. Всегда подтверждайте обновление, сдвигая `offset` за него, иначе Telegram пришлёт его снова.

## Лимиты

| Лимит | Значение |
|---|---|
| Сообщений в один чат | ~1 в секунду |
| Сообщений всего | ~30 в секунду |
| Сообщений в одну группу | 20 в минуту |
| Длина сообщения | 4096 символов (длиннее — делить) |

На `429` прочитайте `parameters.retry_after` и подождите столько секунд.

## Форматирование

Безопаснее всего простой текст. С `parse_mode: "MarkdownV2"` эти символы нужно экранировать `\`: `_ * [ ] ( ) ~ ` > # + - = | { } . !`. Одна неэкранированная `.` — и отправка целиком падает с 400. В режиме `HTML` экранируются только `<`, `>`, `&`.

## Группы и режим приватности

По умолчанию бот в группе видит только команды и ответы на свои сообщения (режим приватности включён). Чтобы отвечать на свободные вопросы в группе, выключите режим приватности в @BotFather (`/setprivacy`) — тогда бот видит все сообщения, так что прямо скажите об этом группе. `faq_bot.py` группы полностью игнорирует; при необходимости доработайте `handle()`.

## Вебхук (только когда опроса не хватает)

```bash
curl -sS "https://api.telegram.org/bot$TELEGRAM_BOT_TOKEN/setWebhook" \
  -d url=https://bot.example.com/telegram \
  -d secret_token="$TELEGRAM_WEBHOOK_SECRET"
```

Требования: публичный HTTPS на порту 443, 80, 88 или 8443; проверяйте заголовок `X-Telegram-Bot-Api-Secret-Token` в каждом запросе и отклоняйте несовпадения; отвечайте `200` быстро, а работу делайте асинхронно.

## Запуск по-настоящему

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

`/etc/faq-bot.env` содержит `TELEGRAM_BOT_TOKEN=...` и `TELEGRAM_OWNER_CHAT_ID=...`, права `600`, владелец root.

**Docker**

```bash
docker run -d --restart=always --name faq-bot \
  --env-file ./faq-bot.env \
  -v "$PWD":/app -w /app python:3.12-slim \
  python faq_bot.py --run --kb faq.json --state /app/state/state.json
```

## Расширение с Jev и LLM

`faq_bot.py` намеренно без ИИ. Добавляйте ИИ в `handle()`, в месте, где `match()` возвращает `answered: false`:

```python
result = match(kb, text, args.min_score, args.min_margin)
if not result["answered"] and os.environ.get("JEV_API_KEY"):
    # Один Choice Jev по id записей базы + no_match (см. engineering/jev).
    jev = jev_ask({"question": {"text": text}}, {"faq": {
        "type": "choice",
        "instructions": "Какая запись полностью отвечает на `question.text`? no_match, если ни одна.",
        "criteria": {e["id"]: {"what": e["question"], "examples": e.get("phrasings", [])[:3]} for e in kb["entries"]}
                    | {"no_match": {"what": "ни одна запись не отвечает полностью"}},
    }})
    faq = jev["answers"]["faq"]
    top = faq["choice"]
    if top != "no_match" and faq["probabilities"][top] >= 0.75:
        result = {**result, "answered": True, "entry_id": top,
                  "answer": next(e["answer"] for e in kb["entries"] if e["id"] == top)}
```

Черновик LLM генерируйте только для вопросов, которые так и остались без ответа, и **отправляйте его владельцу** вместе с пересланным вопросом («Черновик: … — ответьте на сообщение, чтобы отправить свой вариант»). Клиенту уходит ответ владельца — через уже работающую пересылку. Ограничьте `max_tokens` и давайте LLM только вопрос и 3 лучшие записи базы.
