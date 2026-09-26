# faq-knowledge-base — ответы, на которых стоит бот

> Бот хорош ровно настолько, насколько хороши ответы за ним. Извлекайте реальные вопросы, пишите короткие ответы с датами пересмотра и измеряйте, какую часть реального потока база действительно закрывает.

## Правила

| Правило | Чем обеспечено |
|---|---|
| Записи — из реальных вопросов, крупнейшие группы первыми | `faq_kb_coverage.py` |
| У каждой записи есть id, вопрос и непустой ответ; id уникальны | `faq_kb_linter.py` — код выхода 2 |
| Не меньше 3 формулировок словами клиентов | `faq_kb_linter.py` — предупреждение |
| У фактов есть `review_by`; прошедшие даты отмечаются | `faq_kb_linter.py` — предупреждение |
| Путаемые записи объединяются или разводятся | `faq_kb_linter.py` — сходство ≥ 0.6 |
| Покрытие меряется тем же сопоставлением, что у бота | `faq_kb_coverage.py` |

## Быстрый старт

```bash
cp skills/faq-knowledge-base/assets/faq-template.json faq.json
python skills/faq-knowledge-base/scripts/faq_kb_linter.py faq.json
python skills/faq-knowledge-base/scripts/faq_kb_coverage.py faq.json questions.txt
```

Или скажите **«собери FAQ для моего бота из этих сообщений»** или **«о чём спрашивают клиенты, а бот не знает?»**.

## Что внутри

| Путь | Назначение |
|---|---|
| `skills/faq-knowledge-base/SKILL.md` | Режимы: сбор, улучшение, еженедельное обслуживание |
| `skills/faq-knowledge-base/references/kb-format.md` | Правила полей, как писать ответы, сопоставление, связь с Jev |
| `skills/faq-knowledge-base/assets/faq-template.json` | Стартовая база |
| `skills/faq-knowledge-base/scripts/faq_kb_linter.py` | Оценка состояния 0-100. Без сети |
| `skills/faq-knowledge-base/scripts/faq_kb_coverage.py` | Покрытие в % и кандидаты в новые записи. Без сети |

Используется плагинами `telegram-bot` и `smart-reply-router`.
