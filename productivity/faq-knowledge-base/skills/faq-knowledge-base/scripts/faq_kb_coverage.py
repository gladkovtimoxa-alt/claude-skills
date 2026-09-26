#!/usr/bin/env python3
"""Покрытие базы FAQ — сколько реальных вопросов закрывает база знаний, и группировка остальных.

Runs a list of real incoming questions (a text file, a JSON list, or the
`unanswered` log from telegram-bot's state file) through the same token matcher
the bot uses, reports the answered share, per-entry hit counts, entries that
never match, and groups unanswered questions into clusters — each cluster is a
candidate for a new KB entry. No network calls.

Exit codes: 0 = coverage at or above --target, 1 = below target, 2 = bad input.
"""

import argparse
import json
import re
import sys

WORD = re.compile(r"\w+", re.UNICODE)
CLUSTER_SIMILARITY = 0.5
STOPWORDS = {
    "a", "an", "the", "is", "are", "do", "does", "i", "you", "we", "to", "of", "for", "in", "on", "and", "or",
    "can", "how", "what", "my", "me", "it", "be", "with", "please", "hi", "hello",
    "и", "в", "во", "на", "не", "а", "но", "что", "как", "я", "мы", "вы", "ты", "у", "с", "со", "по", "к",
    "за", "из", "о", "об", "это", "ли", "же", "бы", "мне", "вам", "нам", "есть", "можно", "здравствуйте",
    "привет", "пожалуйста", "подскажите", "скажите",
}

SAMPLE_KB = {"entries": [
    {"id": "faq_prices", "question": "Сколько стоит подписка?", "phrasings": ["цена", "сколько стоит", "стоимость тарифа"],
     "answer": "990 ₽/мес"},
    {"id": "faq_reset_pw", "question": "Как сбросить пароль?", "phrasings": ["забыл пароль", "не могу войти"],
     "answer": "Нажмите «Забыли пароль?»"},
    {"id": "faq_hours", "question": "Когда вы работаете?", "phrasings": ["часы работы", "график"],
     "answer": "Будни 10-19"},
]}
SAMPLE_QUESTIONS = [
    "сколько стоит тариф про", "цена за год?", "забыл пароль", "не могу войти в аккаунт",
    "есть ли доставка в Казань", "доставка в Казань сколько дней", "доставляете в Казань?",
    "можно оплатить по счёту для юрлица", "оплата по счёту юрлицо", "как удалить аккаунт",
]


def tokens(text):
    return {w[:5] for w in WORD.findall(str(text).lower()) if w not in STOPWORDS and len(w) > 1}


def dice(a, b):
    return 2 * len(a & b) / (len(a) + len(b)) if a and b else 0.0


def match(entries, question, min_score, min_margin):
    q = tokens(question)
    scored = sorted(
        ((round(100 * max((dice(q, tokens(v)) for v in [e.get("question", "")] + list(e.get("phrasings") or []) if v),
                          default=0.0)), e["id"]) for e in entries),
        reverse=True)
    top = scored[0] if scored else (0, None)
    second = scored[1][0] if len(scored) > 1 else 0
    ok = top[1] is not None and top[0] >= min_score and top[0] - second >= min_margin
    return (top[1] if ok else None), top[0]


def cluster(questions):
    clusters = []
    for q in questions:
        t = tokens(q)
        for c in clusters:
            if dice(t, c["tokens"]) >= CLUSTER_SIMILARITY:
                c["questions"].append(q)
                c["tokens"] |= t
                break
        else:
            clusters.append({"tokens": set(t), "questions": [q]})
    clusters.sort(key=lambda c: len(c["questions"]), reverse=True)
    return [{"size": len(c["questions"]), "example": c["questions"][0], "questions": c["questions"]} for c in clusters]


def load_questions(path):
    if path.endswith(".json"):
        data = json.load(open(path, encoding="utf-8"))
        if isinstance(data, dict) and "unanswered" in data:
            data = data["unanswered"]
        if not isinstance(data, list):
            raise ValueError("JSON вопросов должен быть списком или файлом состояния бота с `unanswered`")
        return [d["text"] if isinstance(d, dict) else str(d) for d in data if d]
    with open(path, encoding="utf-8") as f:
        return [line.strip() for line in f if line.strip()]


def main():
    parser = argparse.ArgumentParser(description="Покрытие базы FAQ на реальных вопросах и группировка неотвеченных. Без сети.")
    parser.add_argument("kb", nargs="?", help="JSON-файл базы")
    parser.add_argument("questions", nargs="?", help="вопросы: .txt (по одному в строке), JSON-список или файл состояния telegram-bot")
    parser.add_argument("--sample", action="store_true", help="запуск на встроенной базе и 10 примерах вопросов")
    parser.add_argument("--min-score", type=int, default=50, help="оценка совпадения 0-100, при которой вопрос считается отвеченным (у бота по умолчанию 50)")
    parser.add_argument("--min-margin", type=int, default=10, help="отрыв от второй записи (у бота по умолчанию 10)")
    parser.add_argument("--target", type=float, default=60.0, help="целевое покрытие в %% для кода выхода")
    parser.add_argument("--json", action="store_true", help="вывод в JSON")
    args = parser.parse_args()

    try:
        if args.sample:
            kb, questions = SAMPLE_KB, SAMPLE_QUESTIONS
        elif args.kb and args.questions:
            kb = json.load(open(args.kb, encoding="utf-8"))
            questions = load_questions(args.questions)
        else:
            parser.error("укажите файлы базы и вопросов или --sample")
        entries = [e for e in kb.get("entries", []) if isinstance(e, dict) and e.get("id")]
        if not entries:
            raise ValueError("в базе нет пригодных записей")
    except (OSError, json.JSONDecodeError, ValueError, AttributeError, KeyError, TypeError) as exc:
        print(f"ошибка: {exc}", file=sys.stderr)
        sys.exit(2)

    hits = {e["id"]: 0 for e in entries}
    unanswered = []
    for q in questions:
        eid, _ = match(entries, q, args.min_score, args.min_margin)
        if eid:
            hits[eid] += 1
        else:
            unanswered.append(q)
    total = len(questions)
    coverage = round(100 * (total - len(unanswered)) / total, 1) if total else 0.0
    clusters = cluster(unanswered)
    result = {
        "questions": total,
        "answered": total - len(unanswered),
        "coverage_pct": coverage,
        "target_pct": args.target,
        "entry_hits": hits,
        "never_matched": [k for k, v in hits.items() if v == 0],
        "new_entry_candidates": clusters,
    }
    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print(f"Покрытие {coverage}% ({result['answered']}/{total}), цель {args.target}%")
        print("Попадания: " + ", ".join(f"{k}={v}" for k, v in sorted(hits.items(), key=lambda x: -x[1])))
        if result["never_matched"]:
            print("Ни разу не сработали (проверьте формулировки или удалите): " + ", ".join(result["never_matched"]))
        if clusters:
            print("Кандидаты в новые записи (крупные первыми):")
            for c in clusters[:10]:
                print(f"  {c['size']}x  например: \"{c['example']}\"")
    sys.exit(0 if coverage >= args.target else 1)


if __name__ == "__main__":
    main()
