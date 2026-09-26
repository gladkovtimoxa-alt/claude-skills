#!/usr/bin/env python3
"""Reply route planner — route triaged messages to ignore / human / faq_template / llm_draft.

Input is a list of messages, each carrying the `answers` object that Jev
returned for the triage batch (intent, faq_match, urgency, is_spam,
needs_human). Rules run in a fixed order: spam, red lines, needs-human,
critical urgency, FAQ gate, LLM draft. Nothing is sent unless the policy
mode is `auto`, the intent is whitelisted and not a red line, and the reply
is a KB template. LLM drafts are never marked for sending. No network calls.

Exit codes: 0 = routed, 1 = some messages need the human, 2 = bad input.
"""

import argparse
import json
import sys

NO_MATCH_KEYS = {"no_match", "none", "nomatch", "other", "no-match"}
RED_LINE_SECONDARY_P = 0.3

DEFAULT_POLICY = {
    "mode": "draft",
    "red_line_intents": ["refund", "legal", "complaint", "personal"],
    "auto_send_intents": [],
    "thresholds": {
        "spam": 0.9,
        "needs_human": 0.6,
        "intent_min_p": 0.55,
        "faq_min_p": 0.75,
        "faq_min_presence": 0.8,
        "critical_urgency": 1.5,
    },
}


def choice(intent, probs, confidence=0.8):
    return {"choice": intent, "probabilities": probs, "confidence": confidence}


SAMPLE_MESSAGES = [
    {"id": "m1", "channel": "email", "answers": {
        "intent": choice("pricing", {"pricing": 0.88, "how_to": 0.07, "refund": 0.02, "no_match": 0.03}),
        "faq_match": choice("faq_prices", {"faq_prices": 0.9, "faq_hours": 0.04, "no_match": 0.06}),
        "urgency": {"score": 0.2}, "is_spam": 0.02, "needs_human": 0.08}},
    {"id": "m2", "channel": "telegram", "answers": {
        "intent": choice("refund", {"refund": 0.81, "pricing": 0.1, "no_match": 0.09}),
        "faq_match": choice("no_match", {"faq_prices": 0.2, "no_match": 0.8}),
        "urgency": {"score": 1.2}, "is_spam": 0.01, "needs_human": 0.77}},
    {"id": "m3", "channel": "slack", "answers": {
        "intent": choice("how_to", {"how_to": 0.64, "bug": 0.3, "no_match": 0.06}),
        "faq_match": choice("faq_reset_pw", {"faq_reset_pw": 0.52, "no_match": 0.48}),
        "urgency": {"score": 0.6}, "is_spam": 0.03, "needs_human": 0.12}},
    {"id": "m4", "channel": "email", "answers": {
        "intent": choice("no_match", {"no_match": 0.9, "pricing": 0.1}),
        "faq_match": choice("no_match", {"no_match": 0.97, "faq_hours": 0.03}),
        "urgency": {"score": 0.0}, "is_spam": 0.96, "needs_human": 0.02}},
    {"id": "m5", "channel": "email", "answers": {
        "intent": choice("pricing", {"pricing": 0.6, "refund": 0.35, "no_match": 0.05}),
        "faq_match": choice("faq_prices", {"faq_prices": 0.85, "no_match": 0.15}),
        "urgency": {"score": 0.4}, "is_spam": 0.01, "needs_human": 0.2}},
    {"id": "m6", "channel": "telegram", "answers": {
        "intent": choice("how_to", {"how_to": 0.93, "bug": 0.04, "no_match": 0.03}),
        "faq_match": choice("faq_hours", {"faq_hours": 0.92, "no_match": 0.08}),
        "urgency": {"score": 0.1}, "is_spam": 0.0, "needs_human": 0.05}},
]

SAMPLE_POLICY = {"mode": "auto", "auto_send_intents": ["pricing", "how_to"]}


def as_prob(value):
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, dict):
        for key in ("probability", "value", "p", "noul"):
            if isinstance(value.get(key), (int, float)):
                return float(value[key])
    return None


def top_of(answer):
    if not isinstance(answer, dict):
        return None, 0.0, {}
    probs = {str(k): float(v) for k, v in (answer.get("probabilities") or {}).items()}
    top = answer.get("choice")
    if top is None and probs:
        top = max(probs, key=probs.get)
    return (str(top) if top is not None else None), probs.get(str(top), 0.0), probs


def no_match_p(probs):
    return sum(p for k, p in probs.items() if k.lower() in NO_MATCH_KEYS)


def route_message(msg, policy):
    t = policy["thresholds"]
    answers = msg.get("answers") or {}
    red = {i.lower() for i in policy["red_line_intents"]}
    whitelist = {i.lower() for i in policy["auto_send_intents"]} - red

    intent, intent_p, intent_probs = top_of(answers.get("intent"))
    faq, faq_p, faq_probs = top_of(answers.get("faq_match"))
    spam = as_prob(answers.get("is_spam"))
    needs_human = as_prob(answers.get("needs_human"))
    urgency = answers.get("urgency") if isinstance(answers.get("urgency"), dict) else {}
    urgency_score = urgency.get("score")

    base = {"id": msg.get("id"), "channel": msg.get("channel"), "intent": intent,
            "intent_p": round(intent_p, 3), "faq": None, "send": False}

    if spam is not None and spam >= t["spam"]:
        return {**base, "route": "ignore", "reason": f"is_spam={spam:.2f}"}
    red_hits = sorted(k for k, p in intent_probs.items() if k.lower() in red and p >= RED_LINE_SECONDARY_P)
    if (intent and intent.lower() in red) or red_hits:
        hit = intent if intent and intent.lower() in red else red_hits[0]
        return {**base, "route": "human", "reason": f"red-line intent '{hit}' (p={intent_probs.get(hit, 0):.2f})"}
    if needs_human is not None and needs_human >= t["needs_human"]:
        return {**base, "route": "human", "reason": f"needs_human={needs_human:.2f}"}
    if isinstance(urgency_score, (int, float)) and urgency_score >= t["critical_urgency"]:
        return {**base, "route": "human", "reason": f"urgency={urgency_score}"}

    presence = 1.0 - no_match_p(faq_probs) if faq_probs else 0.0
    faq_ok = (faq is not None and faq.lower() not in NO_MATCH_KEYS
              and faq_p >= t["faq_min_p"] and presence >= t["faq_min_presence"])
    if faq_ok:
        send = (policy["mode"] == "auto" and intent is not None and intent.lower() in whitelist
                and intent_p >= t["intent_min_p"])
        why = "auto-send: whitelisted intent" if send else "draft: " + (
            "mode is draft" if policy["mode"] != "auto" else
            "intent not whitelisted" if not intent or intent.lower() not in whitelist else
            f"intent p={intent_p:.2f} < {t['intent_min_p']}")
        return {**base, "route": "faq_template", "faq": faq, "send": send,
                "reason": f"faq '{faq}' p={faq_p:.2f}, presence={presence:.2f}; {why}"}

    reason = (f"no FAQ answer (top '{faq}' p={faq_p:.2f}, presence={presence:.2f})"
              if faq is not None else "no faq_match answer")
    return {**base, "route": "llm_draft", "reason": reason}


def merge_policy(user):
    policy = json.loads(json.dumps(DEFAULT_POLICY))
    for key in ("mode", "red_line_intents", "auto_send_intents"):
        if key in user:
            policy[key] = user[key]
    policy["thresholds"].update(user.get("thresholds", {}))
    if policy["mode"] not in ("draft", "auto"):
        raise ValueError("policy mode must be 'draft' or 'auto'")
    return policy


def load(path):
    return json.load(sys.stdin if path == "-" else open(path, encoding="utf-8"))


def main():
    parser = argparse.ArgumentParser(description="Route Jev-triaged messages to ignore / human / faq_template / llm_draft. No network calls.")
    parser.add_argument("messages", nargs="?", help="JSON list of {id, channel, answers} ('-' for stdin)")
    parser.add_argument("--policy", help="routing policy JSON (see references/routing-policy.md)")
    parser.add_argument("--sample", action="store_true", help="route an embedded sample of 6 messages")
    parser.add_argument("--json", action="store_true", help="output as JSON")
    args = parser.parse_args()

    try:
        if args.sample:
            messages, user_policy = SAMPLE_MESSAGES, SAMPLE_POLICY
        elif args.messages:
            messages = load(args.messages)
            user_policy = load(args.policy) if args.policy else {}
        else:
            parser.error("give a messages file or --sample")
        if not isinstance(messages, list):
            raise ValueError("messages must be a JSON list")
        policy = merge_policy(user_policy)
        routed = [route_message(m, policy) for m in messages]
    except (OSError, json.JSONDecodeError, ValueError, TypeError, AttributeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        sys.exit(2)

    counts = {r: sum(x["route"] == r for x in routed) for r in ("ignore", "human", "faq_template", "llm_draft")}
    total = len(routed)
    llm_calls = counts["llm_draft"]
    summary = {
        "mode": policy["mode"],
        "total": total,
        "counts": counts,
        "auto_sent": sum(x["send"] for x in routed),
        "llm_calls": llm_calls,
        "llm_calls_avoided": total - llm_calls,
        "llm_share_pct": round(100 * llm_calls / total, 1) if total else 0.0,
        "routes": routed,
    }
    if args.json:
        print(json.dumps(summary, indent=2, ensure_ascii=False))
    else:
        print(f"{total} messages, mode={policy['mode']}: ignore {counts['ignore']} | human {counts['human']} | "
              f"template {counts['faq_template']} ({summary['auto_sent']} auto-sent) | LLM draft {llm_calls}")
        print(f"LLM calls avoided: {summary['llm_calls_avoided']}/{total}")
        for r in routed:
            flag = " [SEND]" if r["send"] else ""
            print(f"  {r['route'].upper():13}{flag} {r['id']} ({r['channel']}, {r['intent']}): {r['reason']}")
    sys.exit(1 if counts["human"] else 0)


if __name__ == "__main__":
    main()
