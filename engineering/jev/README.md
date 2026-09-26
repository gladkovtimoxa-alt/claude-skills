# jev — Typed Decisions Instead of LLM Calls

> Code owns the loop. Jev answers "which one / yes or no / how much" in ~100-500 ms. The LLM only handles alarms.

Jev (TypeSafe System One) is not a text generator: it takes a JSON `state` plus a batch of
questions and returns typed answers with probabilities. This plugin teaches the agent to find
LLM calls that are really decisions, rewrite them as Jev questions with structured criteria,
and gate the answers in code.

## The discipline

| Rule | Enforced by |
|---|---|
| All questions of one step go in one batch request | `SKILL.md` workflow |
| Criteria are `{what, not_for, examples}`, not plain strings | `jev_request_validator.py` — warning |
| Choice has a `no_match` option when nothing-fits is possible | `jev_request_validator.py` — warning |
| Reversible actions gate on `p(top) ≥ 0.55`; dangerous ones on confidence too | `jev_answer_gate.py` |
| Noul 0.4-0.6 is "don't know", never "medium" | `jev_answer_gate.py` — escalates |
| The API key lives in env only (`JEV_API_KEY`) | `SKILL.md` anti-patterns |

## Quick start

```bash
python skills/jev/scripts/jev_request_validator.py --sample
python skills/jev/scripts/jev_answer_gate.py --sample
```

Or just say **"which of my LLM calls can Jev replace?"** or **"write a Jev request that routes these tickets"**.

## What's in the box

| Path | Purpose |
|---|---|
| `skills/jev/SKILL.md` | Workflow: find decision-shaped LLM calls, design questions, gate, escalate |
| `skills/jev/references/api-reference.md` | Endpoint, request/response contract, errors, stdlib/Node clients |
| `skills/jev/references/question-design.md` | Choice / Noul / Score patterns, state design, batching |
| `skills/jev/scripts/jev_request_validator.py` | Lints a request payload (0-100 score). No network |
| `skills/jev/scripts/jev_answer_gate.py` | Response → act / escalate / human per question. No network |

Scripts are stdlib-only and deterministic; the Jev call itself happens in your code with
`JEV_API_KEY` from the environment.
