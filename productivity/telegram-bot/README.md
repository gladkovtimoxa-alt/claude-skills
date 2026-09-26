# telegram-bot — отвечает на то, что знает, остальное передаёт вам

> Telegram-бот на официальном Bot API. Известные вопросы — мгновенный ответ из вашей базы знаний, 0 токенов ИИ. Неизвестные — пересылаются вам; ответьте на пересланное сообщение, и бот доставит ваш ответ.

## Правила

| Правило | Чем обеспечено |
|---|---|
| Токен и id владельца — только из окружения (`TELEGRAM_BOT_TOKEN`, `TELEGRAM_OWNER_CHAT_ID`) | `faq_bot.py` |
| Отвечать только выше порога совпадения и с отрывом от второй записи; иначе пересылать | `faq_bot.py` — `--min-score`, `--min-margin` |
| Ответ владельца доходит до спросившего ответом на его сообщение | карта пересылок в `faq_bot.py` |
| Offset, карта пересылок и журнал неотвеченных переживают перезапуск | файл состояния `faq_bot.py` |
| Соблюдать `retry_after` на 429; делить сообщения длиннее 4096 символов | `faq_bot.py` |
| Текст LLM никогда не уходит клиенту без владельца | `SKILL.md`, `references/bot-api-essentials.md` |

## Быстрый старт

```bash
python skills/telegram-bot/scripts/faq_bot.py --sample                  # офлайн-демо
python skills/telegram-bot/scripts/faq_bot.py --ask "сколько стоит" --kb faq.json
TELEGRAM_BOT_TOKEN=... python skills/telegram-bot/scripts/faq_bot.py --run --kb faq.json
```

## Что внутри

| Путь | Назначение |
|---|---|
| `skills/telegram-bot/SKILL.md` | Режимы: запуск, рост базы, добавление ИИ; правила доверия |
| `skills/telegram-bot/references/bot-api-essentials.md` | BotFather, методы, лимиты, форматирование, группы, вебхук, systemd/Docker, расширение с Jev/LLM |
| `skills/telegram-bot/scripts/faq_bot.py` | Бот: long polling, ответы из базы, пересылка владельцу. Офлайн-режимы `--ask` / `--sample` |

Формат базы знаний — из плагина `faq-knowledge-base`.
