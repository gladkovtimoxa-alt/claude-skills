#!/usr/bin/env python3
"""Jev answer gate — turn a TypeSafe System One response into act / escalate / human per question.

Applies the thresholds that belong in code, not in the model:
reversible actions gate on p(top), dangerous ones on confidence AND p(top),
Choice with a `no_match` option also checks 1 - p(no_match), Noul uses a
yes/no band with an "unsure" middle. Reads a response JSON and an optional
policy JSON; never calls the network.

Exit codes: 0 = every question can act, 1 = something escalates, 2 = bad input.
"""

import argparse
import json
import sys

NO_MATCH_KEYS = {"no_match", "none", "nomatch", "other", "no-match"}

DEFAULT_POLICY = {
    "reversible": {"min_p_top": 0.55, "min_presence": 0.6},
    "dangerous": {"min_p_top": 0.8, "min_confidence": 0.8, "min_presence": 0.8},
    "noul": {"yes": 0.9, "no": 0.1},
}

SAMPLE_RESPONSE = {
    "model": "jev-1.13.0",
    "answers": {
        "category": {"choice": "billing", "probabilities": {"billing": 0.91, "delivery": 0.06, "no_match": 0.03}, "confidence": 0.84},
        "click_target": {"choice": "e41", "probabilities": {"e41": 0.58, "e42": 0.31, "no_match": 0.11}, "confidence": 0.33},
        "send_refund": {"choice": "approve", "probabilities": {"approve": 0.72, "reject": 0.28}, "confidence": 0.44},
        "is_spam": 0.04,
        "task_done": 0.52,
        "urgency": {"score": 1.6, "probabilities": {"0": 0.1, "1": 0.3, "2": 0.6}, "confidence": 0.41,
                    "legend": {"0": "Normal", "1": "Urgent", "2": "Critical"}},
    },
    "usage": {"input_tokens": 1240, "output_tokens": 14},
}

SAMPLE_POLICY = {"questions": {"send_refund": "dangerous"}}


def noul_value(answer):
    if isinstance(answer, (int, float)):
        return float(answer)
    if isinstance(answer, dict):
        for key in ("probability", "value", "p", "noul", "answer"):
            if isinstance(answer.get(key), (int, float)):
                return float(answer[key])
    return None


def gate_distribution(answer, risk, policy):
    probs = answer.get("probabilities") or {}
    top = answer.get("choice")
    if top is None and "score" in answer and probs:
        top = max(probs, key=probs.get)
    p_top = float(probs.get(str(top), 0.0)) if top is not None else 0.0
    confidence = answer.get("confidence")
    rule = policy[risk]
    no_match = next((k for k in probs if k.lower() in NO_MATCH_KEYS), None)
    presence = 1.0 - float(probs[no_match]) if no_match else None

    reasons = []
    if top is not None and no_match and str(top) == no_match:
        return "escalate", p_top, ["model chose no_match: the answer is not among the candidates"]
    if p_top < rule["min_p_top"]:
        reasons.append(f"p(top)={p_top:.2f} < {rule['min_p_top']}")
    if presence is not None and presence < rule["min_presence"]:
        reasons.append(f"1-p(no_match)={presence:.2f} < {rule['min_presence']}")
    if risk == "dangerous":
        if confidence is None:
            reasons.append("dangerous action but no confidence in the answer")
        elif confidence < rule["min_confidence"]:
            reasons.append(f"confidence={confidence:.2f} < {rule['min_confidence']}")
    if reasons:
        return ("human" if risk == "dangerous" else "escalate"), p_top, reasons
    return "act", p_top, [f"p(top)={p_top:.2f} passes the {risk} gate"]


def gate(response, policy):
    answers = response.get("answers")
    if not isinstance(answers, dict):
        raise ValueError("response has no `answers` object")
    risks = policy.get("questions", {})
    results = []
    for qid, answer in answers.items():
        risk = risks.get(qid, "reversible")
        if risk not in ("reversible", "dangerous"):
            raise ValueError(f"policy for {qid!r} must be 'reversible' or 'dangerous'")
        value = noul_value(answer)
        if value is not None and not (isinstance(answer, dict) and "probabilities" in answer):
            band = policy["noul"]
            if value >= band["yes"]:
                decision, reasons = "act", [f"yes with p={value:.2f}"]
            elif value <= band["no"]:
                decision, reasons = "act", [f"no with p(yes)={value:.2f}"]
            else:
                decision = "human" if risk == "dangerous" else "escalate"
                reasons = [f"p(yes)={value:.2f} is in the unsure band ({band['no']}-{band['yes']})"]
            results.append({"question": qid, "type": "noul", "answer": value >= 0.5, "p": round(value, 4),
                            "risk": risk, "decision": decision, "reasons": reasons})
            continue
        if not isinstance(answer, dict):
            results.append({"question": qid, "type": "unknown", "risk": risk, "decision": "escalate",
                            "reasons": ["unrecognised answer shape"]})
            continue
        qtype = "score" if "score" in answer else "choice"
        decision, p_top, reasons = gate_distribution(answer, risk, policy)
        results.append({"question": qid, "type": qtype, "answer": answer.get("choice", answer.get("score")),
                        "p": round(p_top, 4), "risk": risk, "decision": decision, "reasons": reasons})
    return results


def merge_policy(user):
    policy = json.loads(json.dumps(DEFAULT_POLICY))
    for section in ("reversible", "dangerous", "noul"):
        policy[section].update(user.get(section, {}))
    policy["questions"] = user.get("questions", {})
    return policy


def load(path):
    return json.load(sys.stdin if path == "-" else open(path, encoding="utf-8"))


def main():
    parser = argparse.ArgumentParser(description="Gate a Jev response into act / escalate / human per question. No network calls.")
    parser.add_argument("response", nargs="?", help="Jev response JSON file ('-' for stdin)")
    parser.add_argument("--policy", help="policy JSON: {questions: {id: reversible|dangerous}, reversible: {...}, dangerous: {...}, noul: {...}}")
    parser.add_argument("--sample", action="store_true", help="gate an embedded sample response")
    parser.add_argument("--json", action="store_true", help="output as JSON")
    args = parser.parse_args()

    try:
        if args.sample:
            response, user_policy = SAMPLE_RESPONSE, SAMPLE_POLICY
        elif args.response:
            response = load(args.response)
            user_policy = load(args.policy) if args.policy else {}
        else:
            parser.error("give a response file or --sample")
        results = gate(response, merge_policy(user_policy))
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        sys.exit(2)

    counts = {d: sum(r["decision"] == d for r in results) for d in ("act", "escalate", "human")}
    summary = {"counts": counts, "usage": response.get("usage"), "results": results}
    if args.json:
        print(json.dumps(summary, indent=2, ensure_ascii=False))
    else:
        print(f"act {counts['act']} | escalate {counts['escalate']} | human {counts['human']}")
        for r in results:
            print(f"  {r['decision'].upper():8} {r['question']} = {r.get('answer')!r} ({r['risk']}): {'; '.join(r['reasons'])}")
    sys.exit(0 if counts["escalate"] == counts["human"] == 0 else 1)


if __name__ == "__main__":
    main()
