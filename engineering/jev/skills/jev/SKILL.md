---
name: jev
description: "Use when a step in an agent or pipeline is really a typed decision — pick one option, yes/no, or a position on a scale — and an LLM call is being spent on it. Jev (TypeSafe System One) answers such questions in ~100-500 ms with probabilities instead of generated text, so code keeps the control loop and only escalates to an LLM for free text, planning, or unfamiliar situations. Triggers: 'classify tickets/messages', 'route this request', 'pick the right button/element from candidates', 'is this a jailbreak/phishing/spam', 'severity or urgency score', 'rank candidates', 'did the agent finish the task', 'cut LLM calls in my agent loop', 'Jev', 'TypeSafe', 'System One'. NOT for general LLM cost work like caching or model routing (use llm-cost-optimizer). NOT for generating replies (Jev never writes text)."
---

# Jev — typed decisions instead of LLM calls

You are an expert in building AI-powered software where code owns the loop and models only answer narrow questions. Your goal is to move every decision that is really "choose / yes-no / how much" off the LLM and onto Jev, so the system gets faster, cheaper, and easier to test — without losing quality.

Jev (TypeSafe System One, model `jev-latest`) is not a generative LLM. It takes a JSON `state` and a batch of questions and returns, for each question, a typed answer with a probability distribution. It can't write text, can't reason in prose, and never picks the next step itself. Your code turns its answers into `if`s and thresholds.

---

## Before Starting

Pull answers from the conversation and the codebase first. Ask only for what's missing:

1. **Where are the LLM calls today?** Find every call site and what it decides. Anything that returns a label, a boolean, an index, or a number from a fixed set is a Jev candidate.
2. **What happens when a decision is wrong?** Reversible (a tag, a click, a draft) vs. dangerous (payment, deletion, sending). This sets the thresholds.
3. **Is `JEV_API_KEY` available?** It lives in env / secrets only (console: https://console.typesafe.ai). Never in code, logs, or commits.

---

## How This Skill Works

### Mode 1: Replace LLM decisions in an existing system

1. List the LLM call sites. For each, write down the output shape.
2. Keep only the ones whose output is one of: a label from a fixed set (→ **Choice**), a yes/no (→ **Noul**), a level on an ordered scale (→ **Score**).
3. Rewrite each as a Jev question with **structured criteria** (see below). Group all questions asked at the same step into **one batch request**.
4. Put the thresholds in code (table below). Anything under threshold escalates to the old LLM path — you keep the LLM as the fallback, not the default.
5. Log `usage` from every response next to the old LLM token counts. Compare on real traffic before you delete the LLM path.

### Mode 2: Design a new agent loop (code → Jev → LLM on alarm)

```
loop:
  state   = observe()                         # code: DOM snapshot, ticket, message
  answers = jev.ask(state, questions_for_step) # one batch, ~0.1-1 s
  if gate(answers) == "act":       act()        # code does the action
  elif gate(answers) == "escalate": llm.plan()  # rare: low confidence, captcha, need text
  else:                            ask_human()
  if jev.noul("task complete?", evidence_in_state) >= 0.9: break
```

The LLM becomes an alarm handler, not the driver. On the reference browser-agent run (find a hotel ≤10 000 ₽ with breakfast) this took the loop from 8 LLM calls / 28 169 LLM tokens to 0 LLM calls / 12 184 Jev tokens, 43 s → 34 s. 🟢 measured by the source repo on one task; validate on yours.

### Mode 3: Audit a Jev integration that underperforms

Run the request through `scripts/jev_request_validator.py` first — most bad results are string criteria, missing `no_match`, or evidence missing from `state`. Then check thresholds against `scripts/jev_answer_gate.py` output on logged responses.

---

## The three question types

| Type | Answers | Response fields | Use for |
|---|---|---|---|
| `choice` | one option out of up to 255 | `choice`, `probabilities`, `confidence` | routing, classification, picking a UI element or a tool |
| `noul` | probability of "yes", 0…1 | a single number, no confidence | detectors, guardrails, "is the step done?" |
| `score` | position on 2-10 described levels | `score`, `probabilities`, `confidence`, `legend` | urgency, severity, relevance, quality |

Full request/response contract and error codes: [references/api-reference.md](references/api-reference.md).

## Write criteria as structure, not strings

This is the single biggest lever. Same task, measured in the source experiments: string criteria → p≈0.16 on the right option; `{what, not_for, examples}` → p≈0.66-0.99. 🟢

```json
"criteria": {
  "billing":  { "what": "payments, invoices, refunds", "not_for": "delivery status", "examples": ["refund my order"] },
  "orders":   { "what": "order status and delivery",   "not_for": "payments" },
  "no_match": { "what": "none of the above" }
}
```

More patterns (Noul criteria, Score levels with signals, `state` design): [references/question-design.md](references/question-design.md).

## Gate in code

| Situation | Gate | Action |
|---|---|---|
| Reversible action (click, tag, draft) | `p(top) ≥ 0.55` | do it |
| Dangerous action (send, pay, delete) | `confidence ≥ 0.8` **and** `p(top) ≥ 0.8` | do it, else escalate |
| Candidate may be absent | `1 − p(no_match) ≥ 0.6` | proceed, else re-observe / escalate |
| Noul detector | `≥ 0.9` auto, `0.4-0.6` unsure, `≤ 0.1` auto-no | unsure → LLM or human |
| Many near-duplicate options | ignore low confidence, sum duplicates' p | code picks the most actionable node |

`confidence` is concentration of the distribution, not "am I right". It drops with many options and near-duplicates even when the pick is correct — so don't gate reversible actions on it.

## Tools

```bash
# Lint a request before sending it: structure score 0-100 + findings
python3 scripts/jev_request_validator.py request.json
python3 scripts/jev_request_validator.py --sample --json

# Turn a Jev response into act / escalate / human per question
python3 scripts/jev_answer_gate.py response.json --policy policy.json
python3 scripts/jev_answer_gate.py --sample --json
```

Both are stdlib-only and never call the network. The actual call is one `POST https://api.typesafe.ai/v1/systemone` from your own code (curl / fetch / requests) with `Authorization: Bearer $JEV_API_KEY`.

---

## Proactive Triggers

Surface these without being asked:

- **An LLM call returns a label, boolean, or index** → it's a Jev candidate; estimate the calls saved per day.
- **Several LLM calls in a row on the same input** (classify, then check urgency, then check spam) → collapse into one Jev batch.
- **Choice criteria are plain strings** → rewrite to `{what, not_for, examples}` before blaming the model.
- **Choice where "nothing fits" is possible but there's no `no_match` option** → the model is forced to pick something wrong.
- **A dangerous action gated on `p(top)` only** → add a confidence gate and an escalation path.
- **"Task done?" Noul without evidence in `state`** → it will hover near 0.3-0.5; put filters, flags, extracted facts into `state`.

## Output Artifacts

| When you ask for... | You get... |
|---|---|
| "Where can Jev replace my LLM calls?" | Table of call sites → question type → expected calls/tokens saved |
| "Write the Jev request for X" | Ready JSON payload with structured criteria + validator score |
| "Set thresholds" | Per-question gate policy JSON for `jev_answer_gate.py` |
| "Design the agent loop" | Loop skeleton: observe → batch → gate → act / escalate, with escalation triggers |
| "Why is Jev wrong here?" | Validator findings + rewritten criteria + state fixes |

## Anti-Patterns

| Anti-pattern | Why it fails | Instead |
|---|---|---|
| One HTTP call per question | ~10× slower, ~12× more expensive on a 13-question step | One batch per step |
| Asking Jev to write a reply or plan | It returns typed answers only | Jev decides *whether/which*; LLM writes |
| Dumping the whole context into `state` | Noise lowers probabilities; more tokens | Only the named fields the questions reference |
| Meaning in question keys (`"is_refund": {...}`) | The model never sees keys | Put all meaning in `instructions` / `criteria` |
| Treating Noul 0.5 as "medium" | 0.5 means "don't know" | Route 0.4-0.6 to escalation |
| Hard-coding the key | Leaks in git and logs | `JEV_API_KEY` from env / secrets |
| Deleting the LLM path on day one | No fallback for unfamiliar cases | Keep LLM as the escalation branch |

## Communication

Bottom line first (how many LLM calls go away and what it saves), then the per-call-site table, then the thresholds. Tag every number: 🟢 measured on the user's traffic, 🟡 from the reference experiments, 🔴 estimate. Check known weak spots of the current model before criticising it: https://docs.typesafe.ai/model-jaggedness/jev-1.13.md.

## Related Skills

- **llm-cost-optimizer**: For caching, model routing, prompt compression and cost observability. NOT for moving decisions off the LLM entirely — that's this skill.
- **smart-reply-router** (productivity): Uses Jev to triage email/messages and calls an LLM only to draft the replies that need one. NOT a general Jev reference.
- **faq-knowledge-base** (productivity): Builds the Q&A base that Jev Choice can match incoming questions against. NOT for the API itself.
- **telegram-bot** (productivity): A Telegram bot that answers questions; plugs Jev in as the router. NOT for other messengers.
- **desire-map** (marketing): `desire_map_planner.py --jev` emits a ready Choice request that sorts customer messages into 7 value clusters. NOT for the API itself.
