#!/usr/bin/env python3
"""Проверка рекламных обещаний — поиск в тексте рекламы (русском и базово английском) формулировок, нарушающих ФЗ-38 «О рекламе» или эксплуатирующих уязвимую аудиторию.

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
     "why": "Превосходная степень и «первый/№1» требуют объективного актуального подтверждения с критерием и источником.",
     "fix": "Замените измеримым фактом («доставка за 2 часа») или добавьте источник и критерий («№1 по числу отзывов на Яндекс Картах, сентябрь 2026»)."},
    {"id": "outcome_guarantee", "severity": "high",
     "pattern": r"(гарантир\w* (результат|доход|прибыл|заработ|излечен|похуден|трудоустр|успех|выигрыш)|100\s?%\s?(результат|гарантия|эффект|успех)|гарантированн\w* (результат|доход|заработ|эффект|успех)|guaranteed (results?|income|returns?))",
     "law": "ФЗ-38 ст. 5; ст. 28 для финансовых услуг",
     "why": "Результат, который зависит от клиента или рынка, нельзя гарантировать; это вводит в заблуждение и ведёт к возвратам и жалобам.",
     "fix": "Гарантируйте процесс или возврат: «если за 14 дней не подойдёт — вернём деньги»."},
    {"id": "cure_claim", "severity": "high",
     "pattern": r"(вылеч\w*|излеч\w*|избав\w* от (болезн|диабет|гипертон|рака|артрит|боли|депресс)\w*|лекарств\w* от|панацея|без побочн\w*|от всех болезней|cures?\b|no side effects)",
     "law": "ФЗ-38 ст. 5, 24, 25",
     "why": "Обещания излечения запрещены вне зарегистрированных лекарств и медицинских услуг с обязательным предупреждением, а для БАД — полностью.",
     "fix": "Опишите, что это за продукт и что он делает, без лечебных обещаний; добавьте обязательные предупреждения для категории."},
    {"id": "income_promise", "severity": "high",
     "pattern": r"(гарантированн\w* доходн\w*|доходност\w* от \d+|пассивн\w* доход\w*|заработ\w* от \d[\d\s]*(₽|руб|тыс|000)|доход\w* от \d[\d\s]*(₽|руб|тыс|000)|удво\w* (капитал|деньги|доход)\w*|без вложений|без риска|passive income|double your money)",
     "law": "ФЗ-38 ст. 5; ст. 28 (финансовые услуги: без гарантий доходности)",
     "why": "Обещания дохода — основа жалоб на «инфоцыганство», а для финансовых услуг они запрещены.",
     "fix": "Покажите медиану и диапазон реальных результатов с периодом и условиями; скажите, что клиенту нужно вложить (деньги и время)."},
    {"id": "pester_children", "severity": "high",
     "pattern": r"(попрос\w* (маму|папу|родител\w*)|скажи (маме|папе|родителям)|пусть (мама|папа|родители) купят|у всех (ребят|детей|друзей|одноклассников) уже есть|ask your (mom|dad|parents))",
     "law": "ФЗ-38 ст. 6 (защита несовершеннолетних)",
     "why": "Реклама не может побуждать несовершеннолетних уговаривать родителей купить или внушать, что без товара они хуже других.",
     "fix": "Обращайтесь напрямую к родителю: польза для ребёнка и причина купить для самого родителя."},
    {"id": "fear_appeal", "severity": "medium",
     "pattern": r"(пока не поздно|останеш\w* (один|одна|ни с чем|без)|пожалееш\w*|потеряеш\w* (всё|все|деньги|здоровье|семью)|твои дети (будут|останутся)|before it'?s too late)",
     "law": "ФЗ-38 ст. 5 (недобросовестная реклама); этика",
     "why": "Искусственный страх продаёт тревожным людям и больше всего вредит именно им; регуляторы и площадки считают это манипуляцией.",
     "fix": "Назовите реальный риск фактом и предложите конкретный шаг, который его снижает."},
    {"id": "loneliness", "severity": "high",
     "pattern": r"(найд\w* (любовь|свою половинку|пару|вторую половинку) (за \d|гарантир)|больше не будеш\w* (один|одна|одинок)|одиночеств\w* (уйд|исчезн|закончит)\w*)",
     "law": "Этика; ФЗ-38 ст. 5, если результат обещан",
     "why": "Обещание любви или конца одиночества бьёт по одному из самых уязвимых состояний и не может быть выполнено.",
     "fix": "Честно опишите услугу (мероприятия, подбор, размер сообщества) с реалистичными ожиданиями."},
    {"id": "fake_urgency", "severity": "low",
     "pattern": r"(только сегодня|осталось \d+ (мест|штук|шт|дн)|последний шанс|акция заканчивается|успей\w*|only today|last chance)",
     "law": "ФЗ-38 ст. 5, если это неправда",
     "why": "Срочность допустима, только если она реальна; обнуляющиеся таймеры и вечные «последние 3 места» вводят в заблуждение.",
     "fix": "Оставьте только реальные сроки и ограничения, с датой."},
    {"id": "free_conditions", "severity": "low",
     "pattern": r"(бесплатн\w*|в подарок|free\b)",
     "unless_near": r"(при (заказе|покупке|условии|оплате)|от \d|услови|\*)",
     "law": "ФЗ-38 ст. 5 ч. 7 (нельзя умалчивать о существенных условиях)",
     "why": "«Бесплатно» со скрытыми условиями (подписка, минимальный заказ) вводит в заблуждение, если условий нет в рекламе.",
     "fix": "Укажите условия рядом с предложением тем же размером, что и основной текст."},
]

CATEGORY_REQUIRED = {
    "health": [("противопоказан", "«Имеются противопоказания. Необходимо проконсультироваться со специалистом» (ФЗ-38 ст. 24)"),
               ("консультир", "«…проконсультироваться со специалистом» (ФЗ-38 ст. 24)")],
    "supplement": [("не является лекарств", "«Не является лекарственным средством» (ФЗ-38 ст. 25)")],
    "finance": [("не гарантир", "указание, что доходность не гарантируется, и название организации (ФЗ-38 ст. 28)")],
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
                             "why": f"Реклама категории {category} должна содержать: {requirement}.",
                             "fix": f"Добавьте: {requirement}."})
    if online:
        if not re.search(r"(?<!\w)реклама(?!\w)", low):
            findings.append({"rule": "missing_ad_label", "severity": "high", "match": None, "context": None,
                             "law": "ФЗ-38 ст. 18.1 (маркировка интернет-рекламы)",
                             "why": "Интернет-реклама должна быть помечена «Реклама» и содержать данные о рекламодателе.",
                             "fix": "Добавьте «Реклама. <рекламодатель / ИНН или ссылка на сведения о рекламодателе>»."})
        if "erid" not in low:
            findings.append({"rule": "missing_erid", "severity": "high", "match": None, "context": None,
                             "law": "ФЗ-38 ст. 18.1; ЕРИР via ОРД",
                             "why": "Каждому креативу интернет-рекламы до публикации нужен токен erid, полученный через ОРД.",
                             "fix": "Зарегистрируйте креатив в ОРД и добавьте erid=<токен> в ссылку или текст."})
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
    parser = argparse.ArgumentParser(description="Проверка текста рекламы на красные флаги ФЗ-38 «О рекламе» и эксплуатацию уязвимой аудитории. Не юридическая консультация. Без сети.")
    parser.add_argument("file", nargs="?", help="текстовый файл с рекламой ('-' — stdin)")
    parser.add_argument("--text", help="текст рекламы строкой")
    parser.add_argument("--category", choices=["general", "health", "supplement", "finance", "kids", "infobiz"], default="general",
                        help="категория товара; health/supplement/finance добавляют проверку обязательных предупреждений")
    parser.add_argument("--online", action="store_true", help="реклама в интернете: требовать пометку «Реклама» и erid")
    parser.add_argument("--sample", action="store_true", help="проверить встроенный заведомо плохой пример (интернет, инфобизнес)")
    parser.add_argument("--json", action="store_true", help="вывод в JSON")
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
                print(f"ошибка: {exc}", file=sys.stderr)
                sys.exit(2)
        else:
            parser.error("укажите файл, --text или --sample")

    findings = check(text, category, online)
    s = score(findings)
    worst = "high" if any(f["severity"] == "high" for f in findings) else (
        "medium" if any(f["severity"] == "medium" for f in findings) else ("low" if findings else "none"))
    verdict = {"high": "НЕ ПУБЛИКОВАТЬ", "medium": "ИСПРАВИТЬ ДО ПУБЛИКАЦИИ", "low": "ПРОВЕРИТЬ", "none": "КРАСНЫХ ФЛАГОВ НЕ НАЙДЕНО"}[worst]
    result = {"verdict": verdict, "score": s, "category": category, "online": online, "findings": findings,
              "disclaimer": "Автоматическая первичная проверка. Перед публикацией сверьтесь с актуальным текстом ФЗ-38 и практикой ФАС."}
    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print(f"{verdict}  оценка {s}/100  (замечаний: {len(findings)}, категория={category}, интернет={online})")
        for f in findings:
            where = f" «{f['match']}»" if f["match"] else ""
            print(f"  {f['severity'].upper():6} {f['rule']}{where} — {f['law']}")
            print(f"         исправить: {f['fix']}")
        print(result["disclaimer"])
    sys.exit(2 if worst == "high" else (1 if worst == "medium" else 0))


if __name__ == "__main__":
    main()
