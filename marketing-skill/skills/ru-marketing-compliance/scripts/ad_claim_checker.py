#!/usr/bin/env python3
"""Ad claim checker — lint Russian (and basic English) ad copy for claims that break ФЗ-38 «О рекламе» or exploit vulnerable audiences.

Flags unproven superlatives, outcome/income guarantees, cure claims, pressure on
children, fear appeals, loneliness exploitation, fake urgency, and — per
category — missing mandatory disclaimers (medicine, БАД, finance) and missing
online-ad marking («Реклама» + erid). This is a first-pass lint, not legal
advice: verify against the current law before publishing. No network calls.

Exit codes: 0 = no findings above low, 1 = medium findings, 2 = high findings.
"""

import argparse
import json
import re
import sys

RULES = [
    {"id": "superlative", "severity": "medium",
     "pattern": r"(?<!\w)((?!лучш\w*\s+пожелан)лучш\w*|(?<!наи)самы\w+ (дешев|эффективн|надежн|надёжн|быстр|выгодн|качествен)\w*|№\s?1(?!\d)|номер один|перв\w+ в (росси|мир|стран)\w*|лидер\w* (рынка|продаж|отрасли)|best(?!\s*regards)|#1(?!\d)|number one)",
     "law": "ФЗ-38 ст. 5 (недостоверная реклама)",
     "why": "Superlatives and 'first/№1' need objective, current proof with the criterion and source.",
     "fix": "Replace with a measurable fact ('доставка за 2 часа') or add the source and criterion ('№1 по числу отзывов на Яндекс Картах, сентябрь 2026')."},
    {"id": "outcome_guarantee", "severity": "high",
     "pattern": r"(гарантир\w* (результат|доход|прибыл|заработ|излечен|похуден|трудоустр|успех|выигрыш)|100\s?%\s?(результат|гарантия|эффект|успех)|гарантированн\w* (результат|доход|заработ|эффект|успех)|guaranteed (results?|income|returns?))",
     "law": "ФЗ-38 ст. 5; ст. 28 for financial services",
     "why": "An outcome that depends on the customer or the market can't be guaranteed; it's misleading and drives refunds and complaints.",
     "fix": "Guarantee the process or a refund instead: 'если за 14 дней не подойдёт — вернём деньги'."},
    {"id": "cure_claim", "severity": "high",
     "pattern": r"(вылеч\w*|излеч\w*|избав\w* от (болезн|диабет|гипертон|рака|артрит|боли|депресс)\w*|лекарств\w* от|панацея|без побочн\w*|от всех болезней|cures?\b|no side effects)",
     "law": "ФЗ-38 ст. 5, 24, 25",
     "why": "Cure claims are banned outside registered medicines and medical services with the required warning; for БАД they're banned outright.",
     "fix": "Describe what the product is and does without therapeutic promises; add mandatory warnings for the category."},
    {"id": "income_promise", "severity": "high",
     "pattern": r"(гарантированн\w* доходн\w*|доходност\w* от \d+|пассивн\w* доход\w*|заработ\w* от \d[\d\s]*(₽|руб|тыс|000)|доход\w* от \d[\d\s]*(₽|руб|тыс|000)|удво\w* (капитал|деньги|доход)\w*|без вложений|без риска|passive income|double your money)",
     "law": "ФЗ-38 ст. 5; ст. 28 (financial services: no guaranteed returns)",
     "why": "Income promises are the core of 'инфоцыганство' complaints and are banned for financial services.",
     "fix": "Show the median and range of real outcomes with the period and conditions; say what the customer has to invest (money and time)."},
    {"id": "pester_children", "severity": "high",
     "pattern": r"(попрос\w* (маму|папу|родител\w*)|скажи (маме|папе|родителям)|пусть (мама|папа|родители) купят|у всех (ребят|детей|друзей|одноклассников) уже есть|ask your (mom|dad|parents))",
     "law": "ФЗ-38 ст. 6 (защита несовершеннолетних)",
     "why": "Ads may not urge minors to persuade parents to buy or suggest they're inferior without the product.",
     "fix": "Address the parent directly with the child's benefit and the parent's reason to buy."},
    {"id": "fear_appeal", "severity": "medium",
     "pattern": r"(пока не поздно|останеш\w* (один|одна|ни с чем|без)|пожалееш\w*|потеряеш\w* (всё|все|деньги|здоровье|семью)|твои дети (будут|останутся)|before it'?s too late)",
     "law": "ФЗ-38 ст. 5 (недобросовестная реклама); ethics",
     "why": "Manufactured fear converts anxious people and hurts them most; regulators and platforms treat it as manipulation.",
     "fix": "Name the real risk with a fact and offer the concrete step that reduces it."},
    {"id": "loneliness", "severity": "high",
     "pattern": r"(найд\w* (любовь|свою половинку|пару|вторую половинку) (за \d|гарантир)|больше не будеш\w* (один|одна|одинок)|одиночеств\w* (уйд|исчезн|закончит)\w*)",
     "law": "Ethics; ФЗ-38 ст. 5 if the result is promised",
     "why": "Promising love or an end to loneliness targets one of the most vulnerable states and can't be delivered.",
     "fix": "Describe the service honestly (events, matching, community size) with realistic expectations."},
    {"id": "fake_urgency", "severity": "low",
     "pattern": r"(только сегодня|осталось \d+ (мест|штук|шт|дн)|последний шанс|акция заканчивается|успей\w*|only today|last chance)",
     "law": "ФЗ-38 ст. 5 if untrue",
     "why": "Urgency is fine only if it's real; resetting timers and eternal 'last 3 places' are misleading.",
     "fix": "Keep only real deadlines and limits, with the date."},
    {"id": "free_conditions", "severity": "low",
     "pattern": r"(бесплатн\w*|в подарок|free\b)",
     "unless_near": r"(при (заказе|покупке|условии|оплате)|от \d|услови|\*)",
     "law": "ФЗ-38 ст. 5 ч. 7 (no omission of essential conditions)",
     "why": "'Free' with hidden conditions (subscription, minimum order) is misleading if the conditions aren't in the ad.",
     "fix": "State the conditions next to the offer, same size as the main text."},
]

CATEGORY_REQUIRED = {
    "health": [("противопоказан", "«Имеются противопоказания. Необходимо проконсультироваться со специалистом» (ФЗ-38 ст. 24)"),
               ("консультир", "«…проконсультироваться со специалистом» (ФЗ-38 ст. 24)")],
    "supplement": [("не является лекарств", "«Не является лекарственным средством» (ФЗ-38 ст. 25)")],
    "finance": [("не гарантир", "a statement that returns are not guaranteed, plus the provider's name (ФЗ-38 ст. 28)")],
}

SAMPLE_TEXT = (
    "Лучший курс по заработку в Telegram! Гарантированный доход от 100 000 ₽ в месяц без вложений. "
    "Пока не поздно — успей, осталось 3 места. Первое занятие бесплатно."
)


def check(text, category, online):
    low = text.lower().replace("ё", "е")
    findings = []
    for rule in RULES:
        for m in re.finditer(rule["pattern"], low):
            if rule.get("unless_near") and re.search(rule["unless_near"], low[m.end():m.end() + 60]):
                continue
            start = max(0, m.start() - 25)
            findings.append({"rule": rule["id"], "severity": rule["severity"],
                             "match": text[m.start():m.end()], "context": text[start:m.end() + 25].strip(),
                             "law": rule["law"], "why": rule["why"], "fix": rule["fix"]})
    for needle, requirement in CATEGORY_REQUIRED.get(category, []):
        if needle not in low:
            findings.append({"rule": f"missing_{category}_disclaimer", "severity": "high", "match": None, "context": None,
                             "law": requirement.split("(")[-1].rstrip(")") if "(" in requirement else "ФЗ-38",
                             "why": f"{category} ads must carry {requirement}.",
                             "fix": f"Add {requirement}."})
    if online:
        if not re.search(r"(?<!\w)реклама(?!\w)", low):
            findings.append({"rule": "missing_ad_label", "severity": "high", "match": None, "context": None,
                             "law": "ФЗ-38 ст. 18.1 (маркировка интернет-рекламы)",
                             "why": "Online ads must be labelled «Реклама» and name the advertiser.",
                             "fix": "Add «Реклама. <рекламодатель / ИНН or link to advertiser info>»."})
        if "erid" not in low:
            findings.append({"rule": "missing_erid", "severity": "high", "match": None, "context": None,
                             "law": "ФЗ-38 ст. 18.1; ЕРИР via ОРД",
                             "why": "Each online ad creative needs an erid token obtained from an ОРД before publication.",
                             "fix": "Register the creative in an ОРД, add erid=<token> to the link or text."})
    seen = set()
    unique = []
    for f in findings:
        key = (f["rule"], (f["match"] or "").lower())
        if key not in seen:
            seen.add(key)
            unique.append(f)
    return unique


def score(findings):
    penalty = {"high": 25, "medium": 10, "low": 3}
    return max(0, 100 - sum(penalty[f["severity"]] for f in findings))


def main():
    parser = argparse.ArgumentParser(description="Lint ad copy against ФЗ-38 «О рекламе» red flags and vulnerable-audience exploitation. Not legal advice. No network.")
    parser.add_argument("file", nargs="?", help="text file with the ad copy ('-' for stdin)")
    parser.add_argument("--text", help="ad copy as a string")
    parser.add_argument("--category", choices=["general", "health", "supplement", "finance", "kids", "infobiz"], default="general",
                        help="product category; health/supplement/finance add mandatory-disclaimer checks")
    parser.add_argument("--online", action="store_true", help="the ad runs online: require «Реклама» label and erid")
    parser.add_argument("--sample", action="store_true", help="check an embedded, deliberately bad ad (online, infobiz)")
    parser.add_argument("--json", action="store_true", help="output as JSON")
    args = parser.parse_args()

    if args.sample:
        text, category, online = SAMPLE_TEXT, "infobiz", True
    else:
        category, online = args.category, args.online
        if args.text:
            text = args.text
        elif args.file:
            try:
                text = sys.stdin.read() if args.file == "-" else open(args.file, encoding="utf-8").read()
            except OSError as exc:
                print(f"error: {exc}", file=sys.stderr)
                sys.exit(2)
        else:
            parser.error("give a file, --text or --sample")

    findings = check(text, category, online)
    s = score(findings)
    worst = "high" if any(f["severity"] == "high" for f in findings) else (
        "medium" if any(f["severity"] == "medium" for f in findings) else ("low" if findings else "none"))
    verdict = {"high": "DO NOT PUBLISH", "medium": "FIX BEFORE PUBLISHING", "low": "REVIEW", "none": "NO RED FLAGS FOUND"}[worst]
    result = {"verdict": verdict, "score": s, "category": category, "online": online, "findings": findings,
              "disclaimer": "Automated first pass. Verify against the current ФЗ-38 text and ФАС practice before publishing."}
    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print(f"{verdict}  score {s}/100  ({len(findings)} findings, category={category}, online={online})")
        for f in findings:
            where = f" «{f['match']}»" if f["match"] else ""
            print(f"  {f['severity'].upper():6} {f['rule']}{where} — {f['law']}")
            print(f"         fix: {f['fix']}")
        print(result["disclaimer"])
    sys.exit(2 if worst == "high" else (1 if worst == "medium" else 0))


if __name__ == "__main__":
    main()
