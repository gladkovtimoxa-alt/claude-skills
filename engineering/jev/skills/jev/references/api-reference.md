# Справочник API Jev

Источник истины — живая документация: https://docs.typesafe.ai/llms.txt (страницы в формате `.md`, начинать отсюда). Этот файл — сжатая офлайн-копия для агента.

## Endpoint

Один endpoint, без состояния и истории диалога:

```http
POST https://api.typesafe.ai/v1/systemone
Authorization: Bearer <JEV_API_KEY>
Content-Type: application/json
```

```json
{
  "model": "jev-latest",
  "state": { "ticket": { "text": "..." } },
  "questions": {
    "my_id": { "type": "choice", "instructions": "...", "criteria": { } }
  }
}
```

| Поле | Правило |
|---|---|
| `model` | `jev-latest` (алиас) или закреплённая версия, например `jev-1.13.0`. В продакшене закрепляй версию, чтобы поведение не менялось само. |
| `state` | Любой JSON. Только контекст, нужный вопросам, именованными полями. На вложенные значения ссылайся в инструкциях через обратные кавычки: `` `ticket.messages[0].text` ``. |
| `questions` | Карта «твой ключ → вопрос». Ответы возвращаются под теми же ключами. **Модель ключей не видит.** |
| `type` | `choice`, `noul` или `score`. |
| `instructions` | Строка или структура (`{question, context, note}`). |
| `criteria` | Строка или структура. Структура почти всегда лучше (см. question-design.md). |

Все вопросы одного запроса выполняются **параллельно и независимо** — вопрос не видит ответов других. Если B зависит от ответа A, это два запроса.

## Ответ

```json
{
  "model": "jev-1.13.0",
  "answers": {
    "category": {
      "choice": "billing",
      "probabilities": { "billing": 0.91, "orders": 0.06, "no_match": 0.03 },
      "confidence": 0.84
    },
    "is_phishing": 0.07,
    "urgency": {
      "score": 1.3,
      "probabilities": { "0": 0.12, "1": 0.71, "2": 0.17 },
      "confidence": 0.62,
      "legend": { "0": "Обычная", "1": "Срочно", "2": "Критично" }
    }
  },
  "usage": { "input_tokens": 812, "output_tokens": 9 }
}
```

Точная форма полей может меняться между версиями — сверяйся с https://docs.typesafe.ai/api.md, когда закрепляешь новую модель.

## Ошибки

| Код | Значение | Что делать |
|---|---|---|
| 401 | Неверный или отсутствующий ключ | Остановиться; исправить `JEV_API_KEY` |
| 422 | Некорректное тело запроса | Прогнать `jev_request_validator.py`; исправить запрос |
| 429 | Превышен лимит запросов | Экспоненциальная задержка, затем повтор |
| 529 | Перегрузка | Задержка; при критичной задержке — запасной путь через LLM |

## Минимальные клиенты

**curl**

```bash
curl -sS https://api.typesafe.ai/v1/systemone \
  -H "Authorization: Bearer $JEV_API_KEY" \
  -H "Content-Type: application/json" \
  -d @request.json
```

**Python (стандартная библиотека)**

```python
import json, os, urllib.request

def jev_ask(state, questions, model="jev-latest"):
    body = json.dumps({"model": model, "state": state, "questions": questions}).encode()
    req = urllib.request.Request(
        "https://api.typesafe.ai/v1/systemone",
        data=body,
        headers={
            "Authorization": f"Bearer {os.environ['JEV_API_KEY']}",
            "Content-Type": "application/json",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.load(resp)
```

**Node ≥ 21 (глобальный fetch)**

```js
export async function jevAsk(state, questions, model = "jev-latest") {
  const res = await fetch("https://api.typesafe.ai/v1/systemone", {
    method: "POST",
    headers: {
      Authorization: `Bearer ${process.env.JEV_API_KEY}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ model, state, questions }),
  });
  if (!res.ok) throw new Error(`Jev ${res.status}`);
  return res.json();
}
```

Официальные SDK: Python https://docs.typesafe.ai/sdk/python.md · JavaScript https://docs.typesafe.ai/sdk/javascript.md

## Что почитать

| Тема | Ссылка |
|---|---|
| Концепция System One | https://docs.typesafe.ai/concepts/system-one.md |
| Как строить на System One | https://docs.typesafe.ai/concepts/how-to-build-with-system-one.md |
| Устройство state | https://docs.typesafe.ai/concepts/state.md |
| Примитивы (choice / noul / score) | https://docs.typesafe.ai/primitives.md |
| Структурные instructions и criteria | https://docs.typesafe.ai/primitives/advanced.md |
| Confidence | https://docs.typesafe.ai/confidence.md |
| Паттерны: fan-out, маршрутизация по уверенности, составная оценка, маршрутизация по намерению | https://docs.typesafe.ai/patterns.md |
| Карта применений | https://docs.typesafe.ai/concepts/use-case-map.md |
| Известные слабые места jev-1.13 | https://docs.typesafe.ai/model-jaggedness/jev-1.13.md |
| Playground | https://console.typesafe.ai |
| Рабочие демо (браузерный агент, классификатор тикетов, пикер элементов) | https://github.com/gmoreva/jev-scripts |
