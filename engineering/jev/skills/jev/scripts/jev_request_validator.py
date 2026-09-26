#!/usr/bin/env python3
"""Jev request validator — lint a TypeSafe System One request payload before sending it.

Checks structure (model, state, questions, types, criteria shapes, option limits)
and the quality patterns that decide answer probabilities in practice:
structured criteria over plain strings, a `no_match` escape option on Choice,
described Score levels, meaning outside question keys. Never calls the network.

Exit codes: 0 = clean, 1 = warnings only, 2 = errors (the API would reject it
or answers will be unreliable).
"""

import argparse
import json
import sys

VALID_TYPES = {"choice", "noul", "score"}
NO_MATCH_KEYS = {"no_match", "none", "nomatch", "other", "no-match"}
MAX_CHOICE_OPTIONS = 255
SCORE_MIN_LEVELS, SCORE_MAX_LEVELS = 2, 10
BATCH_SOFT_LIMIT = 40
STATE_SOFT_LIMIT_CHARS = 20000

SAMPLE = {
    "model": "jev-latest",
    "state": {"ticket": {"text": "I was charged twice for order 1182, please refund"}},
    "questions": {
        "category": {
            "type": "choice",
            "instructions": "Which team should handle `ticket.text`?",
            "criteria": {
                "billing": {"what": "payments, invoices, refunds", "not_for": "delivery", "examples": ["refund please"]},
                "delivery": "shipping and parcels",
            },
        },
        "is_spam": {"type": "noul", "instructions": "Is `ticket.text` spam or advertising?"},
        "urgency": {
            "type": "score",
            "instructions": "How urgent is `ticket.text`?",
            "criteria": [
                {"what": "Normal", "signals": ["work not blocked"]},
                {"what": "Critical", "signals": ["money at risk", "work stopped"]},
            ],
        },
    },
}


def add(findings, severity, question, message, penalty):
    findings.append({"severity": severity, "question": question, "message": message, "penalty": penalty})


def is_structured(value):
    return isinstance(value, (dict, list))


def check_choice(qid, q, findings):
    criteria = q.get("criteria")
    if not isinstance(criteria, dict) or not criteria:
        add(findings, "error", qid, "choice needs `criteria` as an object mapping option -> description", 25)
        return
    if len(criteria) > MAX_CHOICE_OPTIONS:
        add(findings, "error", qid, f"{len(criteria)} options; the limit is {MAX_CHOICE_OPTIONS}", 25)
    if len(criteria) < 2:
        add(findings, "error", qid, "choice with fewer than 2 options is not a decision", 20)
    plain = [k for k, v in criteria.items() if isinstance(v, str)]
    if plain:
        add(findings, "warning", qid,
            f"{len(plain)}/{len(criteria)} options use plain-string criteria ({', '.join(plain[:5])}); "
            "use {what, not_for, examples} — measured p rises from ~0.16 to 0.66-0.99", 10)
    structured = [v for v in criteria.values() if isinstance(v, dict)]
    if structured and not any("not_for" in v for v in structured):
        add(findings, "info", qid, "no option has `not_for`; contrast between neighbours sharpens the distribution", 3)
    if not NO_MATCH_KEYS.intersection(k.lower() for k in criteria):
        add(findings, "warning", qid, "no `no_match` option; if nothing-fits is possible the model is forced into a wrong pick", 8)


def check_noul(qid, q, findings):
    criteria = q.get("criteria")
    if criteria is None:
        add(findings, "warning", qid, "noul without criteria; describe what counts as true and false", 6)
    elif isinstance(criteria, dict) and not {"true", "false"}.issubset(criteria):
        add(findings, "info", qid, "noul criteria usually work best as {true: ..., false: ...}", 3)


def check_score(qid, q, findings):
    criteria = q.get("criteria")
    if not isinstance(criteria, list):
        add(findings, "error", qid, "score needs `criteria` as an ordered list of levels", 25)
        return
    n = len(criteria)
    if n < SCORE_MIN_LEVELS or n > SCORE_MAX_LEVELS:
        add(findings, "error", qid, f"{n} levels; score needs {SCORE_MIN_LEVELS}-{SCORE_MAX_LEVELS}", 20)
    for i, level in enumerate(criteria):
        text = level if isinstance(level, str) else json.dumps(level, ensure_ascii=False)
        if text.strip().lstrip("-").replace(".", "", 1).isdigit():
            add(findings, "warning", qid, f"level {i} is a bare number; describe the situation instead", 8)
        elif isinstance(level, str):
            add(findings, "info", qid, f"level {i} is a plain string; {{what, signals}} works better", 2)


def validate(payload):
    findings = []
    if not isinstance(payload, dict):
        add(findings, "error", None, "payload must be a JSON object", 100)
        return findings
    if "model" not in payload:
        add(findings, "error", None, "missing `model` (use jev-latest or a pinned version)", 15)
    elif payload["model"] == "jev-latest":
        add(findings, "info", None, "`jev-latest` floats; pin a version in production", 2)
    if "state" not in payload:
        add(findings, "error", None, "missing `state`", 15)
    elif len(json.dumps(payload["state"], ensure_ascii=False)) > STATE_SOFT_LIMIT_CHARS:
        add(findings, "warning", None, "state is large; pass only the fields questions reference", 8)

    questions = payload.get("questions")
    if not isinstance(questions, dict) or not questions:
        add(findings, "error", None, "`questions` must be a non-empty object keyed by your ids", 40)
        return findings
    if len(questions) > BATCH_SOFT_LIMIT:
        add(findings, "info", None, f"{len(questions)} questions in one batch; fine if they all belong to this step", 0)

    for qid, q in questions.items():
        if not isinstance(q, dict):
            add(findings, "error", qid, "question must be an object", 20)
            continue
        qtype = q.get("type")
        if qtype not in VALID_TYPES:
            add(findings, "error", qid, f"type {qtype!r} is not one of {sorted(VALID_TYPES)}", 20)
            continue
        instructions = q.get("instructions")
        if not instructions:
            add(findings, "error", qid, "missing `instructions`; the model never sees the key, meaning must be here", 15)
        elif isinstance(instructions, str) and len(instructions.split()) < 3:
            add(findings, "warning", qid, "instructions are a couple of words; the key name carries no meaning to the model", 5)
        {"choice": check_choice, "noul": check_noul, "score": check_score}[qtype](qid, q, findings)
    return findings


def score_of(findings):
    return max(0, 100 - sum(f["penalty"] for f in findings))


def main():
    parser = argparse.ArgumentParser(description="Lint a Jev (TypeSafe System One) request payload. No network calls.")
    parser.add_argument("file", nargs="?", help="request JSON file ('-' for stdin)")
    parser.add_argument("--sample", action="store_true", help="validate an embedded sample request")
    parser.add_argument("--json", action="store_true", help="output as JSON")
    args = parser.parse_args()

    if args.sample:
        payload = SAMPLE
    elif args.file:
        try:
            payload = json.load(sys.stdin if args.file == "-" else open(args.file, encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            print(f"error: cannot read request: {exc}", file=sys.stderr)
            sys.exit(2)
    else:
        parser.error("give a request file or --sample")

    findings = validate(payload)
    score = score_of(findings)
    errors = sum(f["severity"] == "error" for f in findings)
    warnings = sum(f["severity"] == "warning" for f in findings)
    verdict = "REJECT" if errors else ("REVIEW" if warnings else "OK")
    result = {"score": score, "verdict": verdict, "errors": errors, "warnings": warnings, "findings": findings}

    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print(f"Jev request: {verdict}  score {score}/100  ({errors} errors, {warnings} warnings)")
        for f in findings:
            where = f"[{f['question']}] " if f["question"] else ""
            print(f"  {f['severity'].upper():7} {where}{f['message']}")
    sys.exit(2 if errors else (1 if warnings else 0))


if __name__ == "__main__":
    main()
