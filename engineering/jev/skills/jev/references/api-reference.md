# Jev API reference

Source of truth is the live documentation: https://docs.typesafe.ai/llms.txt (pages are plain `.md`, start there). This file is a condensed offline copy for the agent.

## Endpoint

Single endpoint, stateless, no conversation history:

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

| Field | Rule |
|---|---|
| `model` | `jev-latest` (alias) or a pinned version such as `jev-1.13.0`. Pin in production so behaviour doesn't shift under you. |
| `state` | Any JSON. Only the context the questions need, as named fields. Reference nested values in instructions with backticks: `` `ticket.messages[0].text` ``. |
| `questions` | Map of your own keys → question objects. Answers come back under the same keys. **The model never sees the keys.** |
| `type` | `choice`, `noul`, or `score`. |
| `instructions` | String or structure (`{question, context, note}`). |
| `criteria` | String or structure. Structure almost always wins (see question-design.md). |

All questions in one request run **in parallel and independently** — a question can't see another's answer. If B depends on A's answer, that's two requests.

## Response

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
      "legend": { "0": "Normal", "1": "Urgent", "2": "Critical" }
    }
  },
  "usage": { "input_tokens": 812, "output_tokens": 9 }
}
```

Exact field shapes can change between versions — check https://docs.typesafe.ai/api.md when you pin a new model.

## Errors

| Code | Meaning | Handling |
|---|---|---|
| 401 | Bad or missing key | Stop; fix `JEV_API_KEY` |
| 422 | Malformed body | Run `jev_request_validator.py`; fix payload |
| 429 | Rate limited | Exponential backoff, then retry |
| 529 | Overloaded | Backoff; fall back to the LLM path if latency-critical |

## Minimal clients

**curl**

```bash
curl -sS https://api.typesafe.ai/v1/systemone \
  -H "Authorization: Bearer $JEV_API_KEY" \
  -H "Content-Type: application/json" \
  -d @request.json
```

**Python (stdlib)**

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

**Node ≥ 21 (global fetch)**

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

Official SDKs: Python https://docs.typesafe.ai/sdk/python.md · JavaScript https://docs.typesafe.ai/sdk/javascript.md

## Further reading

| Topic | Link |
|---|---|
| Concept: System One | https://docs.typesafe.ai/concepts/system-one.md |
| How to build with it | https://docs.typesafe.ai/concepts/how-to-build-with-system-one.md |
| State design | https://docs.typesafe.ai/concepts/state.md |
| Primitives (choice / noul / score) | https://docs.typesafe.ai/primitives.md |
| Structured instructions & criteria | https://docs.typesafe.ai/primitives/advanced.md |
| Confidence | https://docs.typesafe.ai/confidence.md |
| Patterns: fan-out, confidence routing, composite scoring, intent routing | https://docs.typesafe.ai/patterns.md |
| Use-case map | https://docs.typesafe.ai/concepts/use-case-map.md |
| Known weak spots of jev-1.13 | https://docs.typesafe.ai/model-jaggedness/jev-1.13.md |
| Playground | https://console.typesafe.ai |
| Worked demos (browser agent, ticket classifier, element picker) | https://github.com/gmoreva/jev-scripts |
