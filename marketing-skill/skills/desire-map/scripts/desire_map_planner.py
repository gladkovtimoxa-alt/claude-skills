#!/usr/bin/env python3
"""Планировщик карты желаний — превращает описание сегмента в гипотезы по кластерам ценности с честными углами и флагами риска.

Matches free-text segment descriptions (Russian or English) against a map of
segments -> core desires, groups them into 7 value clusters, and returns for
each: the honest promise, the proof you must show, the red line, and a message
template. Vulnerable segments (children, the poor, the lonely, the anxious,
the elderly) are flagged. `--jev` emits a ready Jev Choice request that
classifies real customer messages into the same clusters. No network calls.

Exit codes: 0 = matched, 1 = nothing matched or a vulnerable segment is involved, 2 = bad input.
"""

import argparse
import json
import re
import sys

CLUSTERS = {
    "A_security": {
        "name": "Безопасность и спокойствие / Safety and peace of mind",
        "promise": "Убрать конкретный риск или неопределённость, которую клиент может назвать",
        "proof": "Гарантии процесса (а не результата), прозрачные условия, политика возврата, отзывы людей в той же ситуации",
        "red_line": "Запугивание, которое придумывает или раздувает угрозу; обещание, что ничего плохого никогда не случится",
        "template": "{segment}: больше не нужно беспокоиться о {risk} — {mechanism}, а если {failure}, то {remedy}.",
    },
    "B_body": {
        "name": "Тело: здоровье, сила, красота, результат / Body: health, strength, looks, performance",
        "promise": "Измеримое изменение за указанный срок для людей с указанной исходной точкой",
        "proof": "Честные «до/после» с условиями, квалификация, сколько людей реально этого достигли",
        "red_line": "Обещания излечения, «без побочных эффектов», стыжение за внешность, БАД под видом лекарства (ФЗ-38 ст. 24, 25)",
        "template": "{segment}: {measurable result} за {period}, если вы {effort} — вот как это сделали {n} человек.",
    },
    "C_ease": {
        "name": "Время и простота / Time and ease",
        "promise": "Меньше шагов, минут и решений",
        "proof": "Сэкономленные минуты, убранные шаги, демонстрация всего процесса",
        "red_line": "Называть клиентов ленивыми в тексте; скрывать усилия, которые всё равно понадобятся",
        "template": "{segment}: {task} за {minutes} минут вместо {old_minutes} — {mechanism}.",
    },
    "D_money": {
        "name": "Деньги и рост / Money and growth",
        "promise": "Инструмент, навык или канал с реалистичным и подтверждённым диапазоном результатов",
        "proof": "Кейсы с цифрами и медианой, а не только лучшие; ROI-калькулятор на данных самого клиента",
        "red_line": "Гарантированный доход или доходность (ФЗ-38 ст. 28 для финансовых услуг), продажа «надежды» людям в финансовой беде, «без вложений», когда вложения нужны",
        "template": "{segment}: {concrete capability} — типичный результат {range} через {period}, медиана {median}. Вот что для этого нужно.",
    },
    "E_status": {
        "name": "Статус и уникальность / Status and uniqueness",
        "promise": "Доступ, признание или обладание, которые действительно ограничены",
        "proof": "Реальные ограничения (размер тиража, происхождение, критерии отбора)",
        "red_line": "Фальшивый дефицит («осталось 3», которое обнуляется), недоказуемые «лучший/№1» (ФЗ-38 ст. 5)",
        "template": "{segment}: {what} — {limit} и почему это ограничено.",
    },
    "F_connection": {
        "name": "Связь и доверие / Connection and trust",
        "promise": "Место, человек или доказательство, которому легко довериться",
        "proof": "Квалификация, размер и активность сообщества, публичные отзывы, прозрачное авторство",
        "red_line": "Эксплуатация одиночества (романтика, «только мы вас понимаем»), фальшивые отзывы, оплаченные отзывы без раскрытия",
        "template": "{segment}: {who/what}, что вы можете проверить сами — {evidence}.",
    },
    "G_experience": {
        "name": "Впечатления и свобода / Experience and freedom",
        "promise": "Яркое впечатление или реальное снятие ограничения",
        "proof": "Настоящие фото/видео, подробная программа или условия, что НЕ включено",
        "red_line": "Давление на детей, чтобы они уговаривали родителей купить (ФЗ-38 ст. 6); «свобода», за которой скрыты долгие обязательства",
        "template": "{segment}: {experience} — что именно входит, а что нет.",
    },
}

SEGMENTS = [
    {"id": "men", "label": "Мужчины (по цели: сила)", "stems": ["мужчин", "мужик", "парн", "men", "male"],
     "desires": ["сила"], "cluster": "B_body", "note": "Сегментируй по цели «хочет стать сильнее», а не по полу."},
    {"id": "women", "label": "Женщины (по цели: красота)", "stems": ["женщин", "девушк", "women", "female"],
     "desires": ["красота"], "cluster": "B_body", "note": "Сегментируй по цели «хочет выглядеть/чувствовать себя лучше», а не по полу."},
    {"id": "children", "label": "Дети", "stems": ["дети", "детей", "детям", "детск", "ребен", "ребён", "школьник", "старшеклассник", "подрост", "kid", "child", "teen"],
     "desires": ["мечта"], "cluster": "G_experience", "vulnerable": True,
     "note": "Платит родитель. Обращайся к родителям; никогда не побуждай детей уговаривать их (ФЗ-38 ст. 6)."},
    {"id": "parents", "label": "Родители", "stems": ["родител", " мама", " мамы", " мам ", " мамам", " мамоч", " папа", " папы", " пап ", " папам", "parent", "mother", "father"],
     "desires": ["спокойствие", "будущее детей"], "cluster": "A_security",
     "note": "Строки 4 и 16 объединены. Продавай проверяемый результат для ребёнка плюс прозрачность для родителя."},
    {"id": "wealthy", "label": "Богатые", "stems": ["богат", "состоятельн", "premium", "wealthy", "hnwi", "rich"],
     "desires": ["безопасность"], "cluster": "A_security", "note": "Конфиденциальность и отсутствие хлопот важнее цены."},
    {"id": "poor", "label": "Люди с низким доходом", "stems": ["бедн", "малоимущ", "низким доход", "низкий доход", "низкого доход", "нуждающ", "безработ", "poor", "low-income", "unemployed"],
     "desires": ["надежда"], "cluster": "D_money", "vulnerable": True,
     "note": "Не продавай надежду. Продавай дешёвый, конкретный, проверяемый шаг (навык, инструмент, экономию) с честными шансами."},
    {"id": "anxious", "label": "Тревожные", "stems": ["тревож", "беспокой", "боятся", "боится", "страхи", "страшно", "anxious", "worried"],
     "desires": ["уверенность"], "cluster": "A_security", "vulnerable": True,
     "note": "Без запугивания. Снижай неопределённость понятными условиями, шагами и возможностью выйти."},
    {"id": "lonely", "label": "Одинокие", "stems": ["одинок", "lonely", "single"],
     "desires": ["любовь"], "cluster": "F_connection", "vulnerable": True,
     "note": "Продавай настоящее сообщество или услугу с честными ожиданиями; никогда не намекай, что любовь гарантирована."},
    {"id": "no_hassle", "label": "Не хотят разбираться (в оригинале «ленивые»)", "stems": ["ленив", " лень", "lazy"],
     "desires": ["простота"], "cluster": "C_ease", "note": "Никогда не называй клиента ленивым в тексте: «без необходимости разбираться»."},
    {"id": "busy", "label": "Занятые", "stems": ["занятые", "занятых", "занятым", "занятой", "занятая", "нет времени", "busy"],
     "desires": ["экономия времени"], "cluster": "C_ease", "note": "Считай сэкономленные минуты."},
    {"id": "tired", "label": "Уставшие", "stems": ["устал", "выгор", "tired", "burnout", "burned out"],
     "desires": ["отдых"], "cluster": "C_ease", "note": "Объединено с «занятыми» и «не хотят разбираться» в один кластер «меньше усилий»."},
    {"id": "ambitious", "label": "Амбициозные", "stems": ["амбици", "карьер", "ambitious", "career"],
     "desires": ["статус"], "cluster": "E_status", "note": "Статус должен быть настоящим: отбор, признание, доступ."},
    {"id": "entrepreneurs", "label": "Предприниматели", "stems": ["предприним", "бизнесмен", "собственник", " ип ", "founder", "entrepreneur", "business owner", "smb"],
     "desires": ["деньги"], "cluster": "D_money", "note": "Деньги = больше выручки, меньше затрат или меньше риска; покажи, что именно и сколько."},
    {"id": "investors", "label": "Инвесторы", "stems": ["инвест", "investor"],
     "desires": ["доходность"], "cluster": "D_money", "note": "Прошлая доходность — не обещание; никакой гарантированной доходности (ФЗ-38 ст. 28)."},
    {"id": "elderly", "label": "Пожилые", "stems": ["пожил", "пенсионер", "старшего возраст", "elderly", "senior", "retire"],
     "desires": ["здоровье"], "cluster": "B_body", "vulnerable": True,
     "note": "Самый высокий риск мошенничества. Без обещаний излечения; вовлекай семью; простые условия."},
    {"id": "young", "label": "Молодые", "stems": ["молод", "студент", "young", "student", "gen z"],
     "desires": ["свобода"], "cluster": "G_experience", "note": "Свобода не должна скрывать долгие договоры или долги."},
    {"id": "companies", "label": "Компании", "stems": ["компан", "b2b", "организац", "корпорат", "company", "enterprise"],
     "desires": ["рост"], "cluster": "D_money", "note": "Покупает человек: см. ЛПР."},
    {"id": "bloggers", "label": "Блогеры", "stems": ["блогер", "автор канал", "креатор", "blogger", "creator", "influencer"],
     "desires": ["заработок"], "cluster": "D_money", "note": "Показывай медианный результат авторов, а не верхний 1%."},
    {"id": "experts", "label": "Эксперты", "stems": ["эксперт", "консультант", "коуч", "expert", "consultant", "coach"],
     "desires": ["доверие"], "cluster": "F_connection", "note": "Доверие строится доказательствами, которые можно показать, а не заявлениями."},
    {"id": "travelers", "label": "Путешественники", "stems": ["путешеств", "турист", "travel", "tourist"],
     "desires": ["эмоции"], "cluster": "G_experience", "note": "Показывай впечатление честно, включая то, что не входит."},
    {"id": "buyers", "label": "Покупатели премиума", "stems": ["покупател", "клиент премиум", "shopper", "buyer"],
     "desires": ["эксклюзивность"], "cluster": "E_status", "note": "Эксклюзивность должна быть проверяемой."},
    {"id": "collectors", "label": "Коллекционеры", "stems": ["коллекцион", "collector"],
     "desires": ["редкость"], "cluster": "E_status", "note": "Происхождение и размер тиража важнее прилагательных."},
    {"id": "athletes", "label": "Спортсмены", "stems": ["спортсмен", "атлет", "бегун", "athlete", "runner"],
     "desires": ["результат"], "cluster": "B_body", "note": "Измеримое изменение результатов с условиями."},
    {"id": "decision_makers", "label": "ЛПР / закупщики (добавлено)", "stems": ["лпр", "закуп", "директор", "руководител", "decision maker", "procurement", "cfo", "cto"],
     "desires": ["отсутствие риска", "отчётность"], "cluster": "A_security",
     "note": "Добавлено: B2B-покупателю важнее «меня не обвинят» и цифры для начальника, чем «рост»."},
    {"id": "beginners", "label": "Новички (добавлено)", "stems": ["новичк", "начинающ", "с нуля", "beginner", "newbie", "from scratch"],
     "desires": ["понятный первый шаг"], "cluster": "C_ease", "note": "Добавлено: продавай первую маленькую победу, а не всю трансформацию."},
    {"id": "sceptics", "label": "Скептики (добавлено)", "stems": ["скептик", "не верят", "сомнева", "sceptic", "skeptic"],
     "desires": ["доказательства"], "cluster": "F_connection", "note": "Добавлено: начинай с доказательств и пробного периода без риска."},
]

SAMPLE_SEGMENTS = [
    "занятые предприниматели, у которых нет времени на маркетинг",
    "родители школьников 10-14 лет",
    "пенсионеры, которые хотят следить за здоровьем",
    "B2B: директора по закупкам в производственных компаниях",
]


def norm(text):
    return " " + re.sub(r"\s+", " ", text.lower().replace("ё", "е")) + " "


def plan(segment_text):
    t = norm(segment_text)
    hits = []
    for seg in SEGMENTS:
        if any(stem.replace("ё", "е") in t for stem in seg["stems"]):
            hits.append(seg)
    clusters = []
    for cid in dict.fromkeys(h["cluster"] for h in hits):
        c = CLUSTERS[cid]
        members = [h for h in hits if h["cluster"] == cid]
        clusters.append({
            "cluster": cid,
            "name": c["name"],
            "segments": [m["label"] for m in members],
            "desires": [d for m in members for d in m["desires"]],
            "honest_promise": c["promise"],
            "proof_required": c["proof"],
            "red_line": c["red_line"],
            "template": c["template"],
            "notes": [m["note"] for m in members],
        })
    vulnerable = [h["label"] for h in hits if h.get("vulnerable")]
    return {
        "segment": segment_text,
        "matched": [h["id"] for h in hits],
        "vulnerable": vulnerable,
        "risk": "high" if vulnerable else ("none" if not hits else "normal"),
        "clusters": clusters,
        "next_step": ("Проверьте на 20+ реальных фразах клиентов до того, как писать тексты (см. references/validation-playbook.md)"
                      if hits else "Сегмент не распознан: опишите ситуацию/триггер или добавьте основы слов в SEGMENTS"),
    }


def jev_request():
    criteria = {}
    for cid, c in CLUSTERS.items():
        examples = [d for s in SEGMENTS if s["cluster"] == cid for d in s["desires"]][:4]
        others = [k for k in CLUSTERS if k != cid][:2]
        criteria[cid] = {"what": f"{c['name']}. Клиент хочет: {c['promise'].lower()}",
                         "not_for": "; ".join(CLUSTERS[o]["name"].split(" / ")[0] for o in others),
                         "examples": examples}
    criteria["no_match"] = {"what": "явного желания нет: фактический вопрос, спам или светская беседа"}
    return {
        "model": "jev-latest",
        "state": {"message": {"text": "<customer message or review text>"}},
        "questions": {
            "desire_cluster": {
                "type": "choice",
                "instructions": "Какое глубинное желание автор `message.text` выражает сильнее всего?",
                "criteria": criteria,
            },
            "is_vulnerable_context": {
                "type": "noul",
                "instructions": "Видно ли в `message.text` финансовые трудности, одиночество, сильную тревогу, страх за здоровье или что автор — ребёнок?",
                "criteria": {"true": "нехватка денег, «я один/одна», паника, страх болезни, несовершеннолетний",
                             "false": "обычный интерес, сравнение, логистика"},
            },
        },
    }


def markdown():
    lines = ["# Кластеры ценности", "", "Сгенерировано командой `scripts/desire_map_planner.py --markdown`. Правьте скрипт, а не этот файл.", ""]
    for cid, c in CLUSTERS.items():
        members = [s for s in SEGMENTS if s["cluster"] == cid]
        lines += [f"## {cid} — {c['name']}", "",
                  f"- **Честное обещание:** {c['promise']}",
                  f"- **Нужные доказательства:** {c['proof']}",
                  f"- **Красная линия:** {c['red_line']}",
                  f"- **Шаблон:** `{c['template']}`", "",
                  "| Сегмент | Желание | Уязвимый | Примечание |", "|---|---|---|---|"]
        for s in members:
            lines.append(f"| {s['label']} | {', '.join(s['desires'])} | {'да' if s.get('vulnerable') else ''} | {s['note']} |")
        lines.append("")
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Сегмент -> гипотезы по кластерам ценности с честными углами и флагами риска. Без сети.")
    parser.add_argument("--segment", action="append", metavar="TEXT", help="описание сегмента (можно несколько раз)")
    parser.add_argument("--list", action="store_true", help="вывести всю карту")
    parser.add_argument("--markdown", action="store_true", help="вывести карту в markdown (перегенерирует references/clusters.md)")
    parser.add_argument("--jev", action="store_true", help="вывести запрос Jev Choice, который раскладывает сообщения клиентов по кластерам")
    parser.add_argument("--sample", action="store_true", help="разобрать 4 встроенных примера сегментов")
    parser.add_argument("--json", action="store_true", help="вывод в JSON")
    args = parser.parse_args()

    if args.markdown:
        print(markdown())
        return
    if args.jev:
        print(json.dumps(jev_request(), indent=2, ensure_ascii=False))
        return
    if args.list:
        data = {"clusters": CLUSTERS, "segments": SEGMENTS}
        if args.json:
            print(json.dumps(data, indent=2, ensure_ascii=False))
        else:
            for cid, c in CLUSTERS.items():
                segs = ", ".join(f"{s['label']} → {'/'.join(s['desires'])}" for s in SEGMENTS if s["cluster"] == cid)
                print(f"{cid}: {c['name']}\n  {segs}")
        return
    texts = SAMPLE_SEGMENTS if args.sample else (args.segment or [])
    if not texts:
        parser.error("укажите --segment TEXT, --sample, --list, --markdown или --jev")

    results = [plan(t) for t in texts]
    if args.json:
        print(json.dumps(results, indent=2, ensure_ascii=False))
    else:
        for r in results:
            flag = f"  ⚠ уязвимые: {', '.join(r['vulnerable'])}" if r["vulnerable"] else ""
            print(f"\n{r['segment']}\n  найдено: {', '.join(r['matched']) or '—'}  риск: {r['risk']}{flag}")
            for c in r["clusters"]:
                print(f"  [{c['cluster']}] {', '.join(c['desires'])}")
                print(f"    обещание:       {c['honest_promise']}")
                print(f"    доказательства: {c['proof_required']}")
                print(f"    никогда:        {c['red_line']}")
                for n in c["notes"]:
                    print(f"    заметка:        {n}")
            print(f"  дальше: {r['next_step']}")
    bad = any(not r["matched"] or r["vulnerable"] for r in results)
    sys.exit(0 if args.sample or not bad else 1)


if __name__ == "__main__":
    main()
