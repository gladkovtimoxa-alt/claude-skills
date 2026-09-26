#!/usr/bin/env python3
"""Линтер базы FAQ — проверка базы вопросов и ответов до того, как из неё начнут отвечать боты и маршрутизаторы.

Checks the JSON format shared by telegram-bot and smart-reply-router: unique
ids, a question and an answer per entry, enough real phrasings, answers that
fit one Telegram message, review dates that haven't passed, and pairs of
entries whose phrasings are so close that a matcher (or Jev) will confuse them.
Outputs a 0-100 health score. No network calls.

Exit codes: 0 = healthy, 1 = warnings, 2 = errors (bots should not load it).
"""

import argparse
import datetime
import json
import re
import sys

WORD = re.compile(r"\w+", re.UNICODE)
ID_RE = re.compile(r"^[a-z0-9][a-z0-9_\-]{1,63}$")
MAX_ANSWER = 4096
LONG_ANSWER = 1200
MIN_PHRASINGS = 3
CONFUSABLE = 0.6
STOPWORDS = {
    "a", "an", "the", "is", "are", "do", "does", "i", "you", "we", "to", "of", "for", "in", "on", "and", "or",
    "can", "how", "what", "my", "me", "it", "be", "with", "please",
    "и", "в", "во", "на", "не", "а", "но", "что", "как", "я", "мы", "вы", "ты", "у", "с", "со", "по", "к",
    "за", "из", "о", "об", "это", "ли", "же", "бы", "мне", "вам", "нам", "есть", "можно",
}

SAMPLE_KB = {
    "meta": {"name": "Sample"},
    "entries": [
        {"id": "faq_prices", "question": "How much does it cost?", "phrasings": ["price", "how much", "cost of plan"],
         "answer": "Basic is $10/month, Pro is $25/month.", "review_by": "2026-01-01"},
        {"id": "faq_pricing", "question": "What does it cost?", "phrasings": ["price list", "how much"],
         "answer": "See our prices page."},
        {"id": "faq_reset_pw", "question": "How do I reset my password?", "phrasings": ["forgot password"],
         "answer": ""},
        {"id": "faq_prices", "question": "Duplicate id", "answer": "x"},
    ],
}


def tokens(text):
    return {w[:5] for w in WORD.findall(str(text).lower()) if w not in STOPWORDS and len(w) > 1}


def dice(a, b):
    return 2 * len(a & b) / (len(a) + len(b)) if a and b else 0.0


def add(findings, severity, entry, message, penalty):
    findings.append({"severity": severity, "entry": entry, "message": message, "penalty": penalty})


def lint(kb, today):
    findings = []
    if not isinstance(kb, dict) or not isinstance(kb.get("entries"), list):
        add(findings, "error", None, "база должна быть объектом со списком `entries`", 100)
        return findings, 0
    entries = kb["entries"]
    if not entries:
        add(findings, "error", None, "в базе нет записей", 100)
        return findings, 0

    seen = {}
    for i, e in enumerate(entries):
        if not isinstance(e, dict):
            add(findings, "error", f"#{i}", "запись должна быть объектом", 15)
            continue
        eid = e.get("id")
        label = eid or f"#{i}"
        if not eid:
            add(findings, "error", label, "нет `id`", 15)
        elif not ID_RE.match(str(eid)):
            add(findings, "warning", label, "id должен состоять из строчных букв, цифр, _ или - (он становится ключом варианта Jev)", 3)
        if eid in seen:
            add(findings, "error", label, f"повтор id (также запись #{seen[eid]})", 15)
        elif eid:
            seen[eid] = i
        if not str(e.get("question", "")).strip():
            add(findings, "error", label, "нет `question`", 10)
        answer = str(e.get("answer", "")).strip()
        if not answer:
            add(findings, "error", label, "пустой `answer` — бот ничего не отправит", 15)
        elif len(answer) > MAX_ANSWER:
            add(findings, "warning", label, f"ответ {len(answer)} символов; Telegram делит сообщения длиннее {MAX_ANSWER}", 5)
        elif len(answer) > LONG_ANSWER:
            add(findings, "info", label, f"ответ {len(answer)} символов; люди читают первые две строки", 1)
        phrasings = e.get("phrasings") or []
        if not isinstance(phrasings, list):
            add(findings, "error", label, "`phrasings` должен быть списком строк", 10)
            phrasings = []
        if len(phrasings) < MIN_PHRASINGS:
            add(findings, "warning", label, f"формулировок: {len(phrasings)}; добавьте хотя бы {MIN_PHRASINGS} словами клиентов", 4)
        review_by = e.get("review_by")
        if review_by:
            try:
                if datetime.date.fromisoformat(str(review_by)) < today:
                    add(findings, "warning", label, f"review_by {review_by} прошёл — факты могли устареть", 6)
            except ValueError:
                add(findings, "warning", label, f"review_by {review_by!r} не в формате YYYY-MM-DD", 2)
        else:
            add(findings, "info", label, "нет `review_by`; цены, даты и правила устаревают незаметно", 1)

    valid = [e for e in entries if isinstance(e, dict) and e.get("id")]
    sets = {id(e): [tokens(v) for v in [e.get("question", "")] + list(e.get("phrasings") or []) if tokens(v)] for e in valid}
    for a_i in range(len(valid)):
        for b_i in range(a_i + 1, len(valid)):
            a, b = valid[a_i], valid[b_i]
            if a["id"] == b["id"]:
                continue
            best = max((dice(x, y) for x in sets[id(a)] for y in sets[id(b)]), default=0.0)
            if best >= CONFUSABLE:
                add(findings, "warning", a["id"],
                    f"легко спутать с '{b['id']}' (сходство {best:.2f}); объедините или сделайте формулировки чётче", 6)

    score = max(0, 100 - sum(f["penalty"] for f in findings))
    return findings, score


def main():
    parser = argparse.ArgumentParser(description="Проверка JSON-базы FAQ (формат telegram-bot / smart-reply-router). Без сети.")
    parser.add_argument("kb", nargs="?", help="JSON-файл базы ('-' — stdin)")
    parser.add_argument("--sample", action="store_true", help="проверить встроенный пример базы с намеренными ошибками")
    parser.add_argument("--today", help="дата для проверки review_by, YYYY-MM-DD (по умолчанию сегодня)")
    parser.add_argument("--json", action="store_true", help="вывод в JSON")
    args = parser.parse_args()

    try:
        today = datetime.date.fromisoformat(args.today) if args.today else datetime.date.today()
        if args.sample:
            kb = SAMPLE_KB
        elif args.kb:
            kb = json.load(sys.stdin if args.kb == "-" else open(args.kb, encoding="utf-8"))
        else:
            parser.error("укажите файл базы или --sample")
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        print(f"ошибка: {exc}", file=sys.stderr)
        sys.exit(2)

    findings, score = lint(kb, today)
    errors = sum(f["severity"] == "error" for f in findings)
    warnings = sum(f["severity"] == "warning" for f in findings)
    entries = len(kb.get("entries", [])) if isinstance(kb, dict) else 0
    verdict = "BROKEN" if errors else ("NEEDS WORK" if warnings else "HEALTHY")
    result = {"entries": entries, "score": score, "verdict": verdict, "errors": errors, "warnings": warnings,
              "findings": findings}
    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print(f"База FAQ: {verdict}  оценка {score}/100  (записей: {entries}, ошибок: {errors}, предупреждений: {warnings})")
        for f in findings:
            where = f"[{f['entry']}] " if f["entry"] else ""
            print(f"  {f['severity'].upper():7} {where}{f['message']}")
    sys.exit(2 if errors else (1 if warnings else 0))


if __name__ == "__main__":
    main()
