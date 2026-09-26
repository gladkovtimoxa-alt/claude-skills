#!/usr/bin/env python3
"""Валидатор запросов Jev — проверка запроса к TypeSafe System One до отправки.

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
        add(findings, "error", qid, "choice требует `criteria` в виде объекта «вариант -> описание»", 25)
        return
    if len(criteria) > MAX_CHOICE_OPTIONS:
        add(findings, "error", qid, f"{len(criteria)} вариантов; лимит {MAX_CHOICE_OPTIONS}", 25)
    if len(criteria) < 2:
        add(findings, "error", qid, "choice меньше чем с 2 вариантами — это не решение", 20)
    plain = [k for k, v in criteria.items() if isinstance(v, str)]
    if plain:
        add(findings, "warning", qid,
            f"{len(plain)}/{len(criteria)} вариантов со строковыми критериями ({', '.join(plain[:5])}); "
            "используйте {what, not_for, examples} — по замерам p растёт с ~0.16 до 0.66-0.99", 10)
    structured = [v for v in criteria.values() if isinstance(v, dict)]
    if structured and not any("not_for" in v for v in structured):
        add(findings, "info", qid, "ни у одного варианта нет `not_for`; контраст с соседями делает распределение чётче", 3)
    if not NO_MATCH_KEYS.intersection(k.lower() for k in criteria):
        add(findings, "warning", qid, "нет варианта `no_match`; если «ничего не подходит» возможно, модель вынуждена выбрать неверное", 8)


def check_noul(qid, q, findings):
    criteria = q.get("criteria")
    if criteria is None:
        add(findings, "warning", qid, "noul без критериев; опишите, что считается true и false", 6)
    elif isinstance(criteria, dict) and not {"true", "false"}.issubset(criteria):
        add(findings, "info", qid, "критерии noul лучше всего работают в виде {true: ..., false: ...}", 3)


def check_score(qid, q, findings):
    criteria = q.get("criteria")
    if not isinstance(criteria, list):
        add(findings, "error", qid, "score требует `criteria` в виде упорядоченного списка уровней", 25)
        return
    n = len(criteria)
    if n < SCORE_MIN_LEVELS or n > SCORE_MAX_LEVELS:
        add(findings, "error", qid, f"{n} уровней; для score нужно {SCORE_MIN_LEVELS}-{SCORE_MAX_LEVELS}", 20)
    for i, level in enumerate(criteria):
        text = level if isinstance(level, str) else json.dumps(level, ensure_ascii=False)
        if text.strip().lstrip("-").replace(".", "", 1).isdigit():
            add(findings, "warning", qid, f"уровень {i} — голое число; опишите ситуацию", 8)
        elif isinstance(level, str):
            add(findings, "info", qid, f"уровень {i} — простая строка; {{what, signals}} работает лучше", 2)


def validate(payload):
    findings = []
    if not isinstance(payload, dict):
        add(findings, "error", None, "запрос должен быть JSON-объектом", 100)
        return findings
    if "model" not in payload:
        add(findings, "error", None, "нет `model` (укажите jev-latest или закреплённую версию)", 15)
    elif payload["model"] == "jev-latest":
        add(findings, "info", None, "`jev-latest` плавающий; в продакшене закрепите версию", 2)
    if "state" not in payload:
        add(findings, "error", None, "нет `state`", 15)
    elif len(json.dumps(payload["state"], ensure_ascii=False)) > STATE_SOFT_LIMIT_CHARS:
        add(findings, "warning", None, "state слишком большой; передавайте только поля, на которые ссылаются вопросы", 8)

    questions = payload.get("questions")
    if not isinstance(questions, dict) or not questions:
        add(findings, "error", None, "`questions` должен быть непустым объектом с вашими ключами", 40)
        return findings
    if len(questions) > BATCH_SOFT_LIMIT:
        add(findings, "info", None, f"{len(questions)} вопросов в одной пачке; нормально, если все относятся к этому шагу", 0)

    for qid, q in questions.items():
        if not isinstance(q, dict):
            add(findings, "error", qid, "вопрос должен быть объектом", 20)
            continue
        qtype = q.get("type")
        if qtype not in VALID_TYPES:
            add(findings, "error", qid, f"тип {qtype!r} не из {sorted(VALID_TYPES)}", 20)
            continue
        instructions = q.get("instructions")
        if not instructions:
            add(findings, "error", qid, "нет `instructions`; модель не видит ключ, смысл должен быть здесь", 15)
        elif isinstance(instructions, str) and len(instructions.split()) < 3:
            add(findings, "warning", qid, "instructions — пара слов; имя ключа для модели ничего не значит", 5)
        {"choice": check_choice, "noul": check_noul, "score": check_score}[qtype](qid, q, findings)
    return findings


def score_of(findings):
    return max(0, 100 - sum(f["penalty"] for f in findings))


def main():
    parser = argparse.ArgumentParser(description="Проверка запроса к Jev (TypeSafe System One). Без сетевых вызовов.")
    parser.add_argument("file", nargs="?", help="JSON-файл запроса ('-' — stdin)")
    parser.add_argument("--sample", action="store_true", help="проверить встроенный пример запроса")
    parser.add_argument("--json", action="store_true", help="вывод в JSON")
    args = parser.parse_args()

    if args.sample:
        payload = SAMPLE
    elif args.file:
        try:
            payload = json.load(sys.stdin if args.file == "-" else open(args.file, encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            print(f"ошибка: не удалось прочитать запрос: {exc}", file=sys.stderr)
            sys.exit(2)
    else:
        parser.error("укажите файл запроса или --sample")

    findings = validate(payload)
    score = score_of(findings)
    errors = sum(f["severity"] == "error" for f in findings)
    warnings = sum(f["severity"] == "warning" for f in findings)
    verdict = "REJECT" if errors else ("REVIEW" if warnings else "OK")
    result = {"score": score, "verdict": verdict, "errors": errors, "warnings": warnings, "findings": findings}

    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print(f"Запрос Jev: {verdict}  оценка {score}/100  (ошибок: {errors}, предупреждений: {warnings})")
        for f in findings:
            where = f"[{f['question']}] " if f["question"] else ""
            print(f"  {f['severity'].upper():7} {where}{f['message']}")
    sys.exit(2 if errors else (1 if warnings else 0))


if __name__ == "__main__":
    main()
