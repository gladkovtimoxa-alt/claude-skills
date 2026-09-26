# smart-reply-router — Reply to Everything, Pay the LLM for Little

> Jev decides which bucket each message is in. Templates answer the known questions. The LLM drafts only what's left. Nothing risky goes out without you.

## The discipline

| Rule | Enforced by |
|---|---|
| Every message is triaged in one Jev batch (intent, FAQ match, urgency, spam, needs-human) | `references/triage-batch.md` |
| Order: spam → red lines → needs-human → critical → FAQ → LLM | `reply_route_planner.py` |
| Refunds, legal, complaints, personal always go to the human — even at 35% probability | `reply_route_planner.py` |
| Mode is `draft` unless the user explicitly opts in to `auto` | `reply_route_planner.py` — default policy |
| Only KB templates can be auto-sent; LLM output is always a draft | `reply_route_planner.py` |
| Keys live in env / secrets | `SKILL.md` anti-patterns |

## Quick start

```bash
python skills/smart-reply-router/scripts/reply_route_planner.py --sample
```

Or say **"set up auto-replies for my support inbox"** or **"answer today's Telegram questions"**.

## What's in the box

| Path | Purpose |
|---|---|
| `skills/smart-reply-router/SKILL.md` | Setup, cost-cutting and scheduled modes; routing table; channel notes |
| `skills/smart-reply-router/references/triage-batch.md` | Ready Jev triage request and planner input format |
| `skills/smart-reply-router/references/routing-policy.md` | Policy fields, rule order, why the defaults are what they are |
| `skills/smart-reply-router/scripts/reply_route_planner.py` | Triaged messages → routes, send flags, LLM calls avoided. No network |

Works with the `jev`, `faq-knowledge-base` and `telegram-bot` plugins.
