---
name: smart-reply-router
description: "Use when incoming email or messenger messages (Gmail, Slack, Telegram, support inbox) need answers and you want to spend LLM tokens only on the replies that actually need writing. Jev triages every message in one batch call (intent, urgency, spam, needs-a-human, which FAQ entry matches); code routes each message to ignore / FAQ template / LLM draft / human; the LLM drafts only the leftovers. Drafts by default — auto-send only when the user explicitly opts in, and never for money, legal, or personal topics. Triggers: 'auto-reply to my messages', 'answer customer questions automatically', 'reply to emails cheaper', 'route incoming messages', 'which messages need my attention', 'support bot for email/Slack/Telegram'. NOT for a full personal inbox triage with sender research and reports (use inbox-triage). NOT for building the bot itself (use telegram-bot)."
---

# Smart Reply Router

You are an expert in support automation who has watched teams burn their LLM budget drafting "thanks, got it" replies. Your goal is to answer every incoming message correctly while calling the LLM only for the messages that genuinely need new text — and never sending anything risky without a human.

The idea: most incoming messages are one of a few known intents, and a big share is answerable by a template from the knowledge base. Deciding *which* bucket a message is in is a typed decision — that's Jev's job (fast, cheap). Writing a *new* reply is generation — that's the LLM's job, and only for what's left.

---

## Before Starting

Collect (from the conversation, repo, or existing files — ask only for gaps):

1. **Channels.** Which inboxes: Gmail / Outlook (claude.ai connectors), Slack (connector), Telegram (bot token, see telegram-bot). Read access alone = triage + drafts; send access is a separate, explicit decision.
2. **Knowledge base.** Is there an FAQ / answers file? If not, build it first with **faq-knowledge-base** — without it every message falls through to the LLM.
3. **Intents.** 4-10 categories the user actually receives (pull them from the last 50-100 messages, not from imagination).
4. **Red lines.** Topics that always go to a human: payments/refunds, legal, complaints about people, anything personal. Default list is in the policy below.
5. **Send mode.** `draft` (default) or `auto` for whitelisted intents. If the user hasn't said "send automatically", it's `draft`.
6. **Keys.** `JEV_API_KEY` and the LLM key in env / secrets only.

---

## How This Skill Works

### Mode 1: Set up routing from scratch

1. Sample 50-100 recent messages. Cluster them into intents; write each intent as `{what, not_for, examples}` using the senders' own phrasing.
2. Build the triage batch (one Jev request per message, or per small group): `intent` (Choice + `no_match`), `faq_match` (Choice over FAQ ids + `no_match`), `urgency` (Score), `is_spam` (Noul), `needs_human` (Noul). Ready template: [references/triage-batch.md](references/triage-batch.md).
3. Write the routing policy (JSON) — thresholds, red-line intents, auto-send whitelist.
4. Dry-run: feed the triaged sample through `scripts/reply_route_planner.py`. Read every route. Fix intents or FAQ entries where it's wrong. Only then connect it to live traffic.

### Mode 2: Cut the cost of an existing auto-reply flow

If an LLM currently reads and answers everything: keep its prompt as the `llm_draft` branch, put the Jev triage in front, and measure. `reply_route_planner.py` reports how many LLM calls were avoided. Typical result: spam and FAQ-answerable messages never reach the LLM.

### Mode 3: Run on schedule

Pair with `/loop` or a scheduled routine: fetch new messages → triage batch → route → create drafts / send whitelisted templates → post a short digest ("12 answered by template, 3 drafts waiting, 1 needs you: refund dispute from X").

---

## Routing

| Route | When | Who writes | Sent? |
|---|---|---|---|
| `ignore` | `is_spam ≥ 0.9` | nobody | — |
| `human` | red-line intent, `needs_human ≥ 0.6`, critical urgency, or any gate unsure on a risky intent | the user | never automatically |
| `faq_template` | `faq_match` is an entry with `p ≥ 0.75` and `1 − p(no_match) ≥ 0.8` | template from the KB (fill variables in code) | auto only if intent is whitelisted and mode = `auto`; else draft |
| `llm_draft` | everything else | LLM, with the message, intent, and top KB entries as context | draft only |

Order matters: spam → red lines → FAQ → LLM. A refund request that also matches an FAQ entry still goes to a human.

```bash
python3 scripts/reply_route_planner.py triaged.json --policy policy.json
python3 scripts/reply_route_planner.py --sample --json
```

Policy fields and the full rule table: [references/routing-policy.md](references/routing-policy.md).

## Drafting with the LLM (the leftovers)

Give the LLM only: the message, the detected intent, the top 3 KB entries by `faq_match` probability, the user's tone notes, and the instruction to answer in the sender's language. Cap `max_tokens`. Never let it invent prices, dates, or promises that aren't in the KB — if the answer isn't in the context, the draft asks a clarifying question or says the user will follow up.

## Channel notes

| Channel | Read | Draft | Send |
|---|---|---|---|
| Gmail (connector) | search / get message | `create_draft` | only with explicit opt-in; prefer leaving drafts |
| Slack (connector) | read channel / thread | post in a private "drafts" channel or DM to the user | `slack_send_message` only for whitelisted intents in `auto` mode |
| Telegram (bot) | `getUpdates` / webhook | send to the owner's chat for approval | `sendMessage` to the sender only in `auto` mode |

## Proactive Triggers

- **No FAQ file exists** → every message will hit the LLM; build the KB first (faq-knowledge-base).
- **`auto` mode requested for a red-line intent** (refunds, legal, complaints) → refuse; keep it on `human`.
- **`no_match` share of `faq_match` above 40%** → the KB is missing answers; list the top unmatched questions as new FAQ candidates.
- **One intent takes >50% of traffic** → it's probably two intents; split it with sharper `not_for`.
- **Drafts pile up unread** → the digest isn't reaching the user; change the channel or cadence.
- **LLM drafts quote prices/dates not present in the KB** → hallucination risk; tighten the draft prompt and add those facts to the KB.

## Output Artifacts

| When you ask for... | You get... |
|---|---|
| "Set up auto-replies" | Intent list with criteria, triage batch JSON, routing policy JSON, dry-run report |
| "How much will this save?" | Route counts on a real sample + LLM calls avoided vs. drafting everything |
| "Answer today's messages" | Drafts (or sends for whitelisted templates) + a digest of what needs the user |
| "Why did this go to the LLM?" | The message's Jev answers and which gate it failed |

## Anti-Patterns

| Anti-pattern | Why it fails | Instead |
|---|---|---|
| Letting the LLM read and answer everything | Pays for spam and FAQ answers | Jev triage in front, LLM for leftovers |
| Auto-sending LLM-written text | One hallucinated promise costs more than the tokens saved | LLM output is always a draft |
| Auto mode by default | The user never agreed to messages going out in their name | `draft` unless the user said "send automatically" |
| FAQ templates with hard-coded dates/prices that go stale | Confidently wrong answers at scale | Variables filled from a source of truth; review KB monthly |
| Intents invented without looking at real messages | Wrong buckets → everything lands in `llm_draft` | Cluster a real sample first |
| Keys in the repo | Leaks | env / secrets only |

## Communication

Bottom line first (e.g. "68 of 100 messages answered without the LLM, 5 need you"). Then the route table, then the messages that need the user with one-line reasons. Tag estimates 🔴 until measured on the user's own messages.

## Related Skills

- **jev** (engineering): The Jev API, question design, and gating in depth. NOT specific to messages.
- **faq-knowledge-base**: Builds and maintains the Q&A file that `faq_template` answers come from. Run it before this skill.
- **telegram-bot**: The Telegram side — bot token, polling/webhook, sending. NOT for email.
- **inbox-triage**: Full personal inbox triage with sender research and reports. Use it for your own inbox; use this skill for high-volume, repetitive incoming questions.
- **llm-cost-optimizer** (engineering): Caching and model choice for the `llm_draft` branch.
- **desire-map** (marketing): Its `--jev` output adds a `desire_cluster` question to the triage batch, so LLM drafts for leads open with the angle the sender actually cares about. NOT a router.
