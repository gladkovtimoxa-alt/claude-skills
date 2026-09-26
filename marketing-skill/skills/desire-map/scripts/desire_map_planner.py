#!/usr/bin/env python3
"""Desire map planner — turn a segment description into value-cluster hypotheses with honest angles and risk flags.

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
        "promise": "Remove a specific risk or uncertainty the customer can name",
        "proof": "Process guarantees (not outcome guarantees), transparent terms, refund policy, reviews from people in the same situation",
        "red_line": "Fear appeals that invent or inflate the threat; promising that nothing bad will ever happen",
        "template": "{segment}: stop worrying about {risk} — {mechanism}, and if {failure}, {remedy}.",
    },
    "B_body": {
        "name": "Тело: здоровье, сила, красота, результат / Body: health, strength, looks, performance",
        "promise": "A measurable change over a stated period, for people with a stated starting point",
        "proof": "Honest before/after with conditions, credentials, how many people actually got there",
        "red_line": "Cure claims, 'no side effects', body shaming, supplements presented as medicine (ФЗ-38 ст. 24, 25)",
        "template": "{segment}: {measurable result} in {period} if you {effort} — here's how {n} people did it.",
    },
    "C_ease": {
        "name": "Время и простота / Time and ease",
        "promise": "Fewer steps, fewer minutes, fewer decisions",
        "proof": "Minutes saved, steps removed, a demo of the whole flow",
        "red_line": "Calling customers lazy in the copy; hiding the effort that is still required",
        "template": "{segment}: {task} in {minutes} minutes instead of {old_minutes} — {mechanism}.",
    },
    "D_money": {
        "name": "Деньги и рост / Money and growth",
        "promise": "A tool, skill or channel with a realistic, sourced range of outcomes",
        "proof": "Cases with numbers and the median, not only the best; an ROI calculator with the customer's own inputs",
        "red_line": "Guaranteed income or returns (ФЗ-38 ст. 28 for financial services), selling 'hope' to people in financial distress, 'no investment needed' when there is one",
        "template": "{segment}: {concrete capability} — typical result {range} after {period}, median {median}. Here's what it takes.",
    },
    "E_status": {
        "name": "Статус и уникальность / Status and uniqueness",
        "promise": "Access, recognition or ownership that really is limited",
        "proof": "Real limits (edition size, provenance, selection criteria)",
        "red_line": "Fake scarcity ('only 3 left' that resets), unverifiable 'best/№1' claims (ФЗ-38 ст. 5)",
        "template": "{segment}: {what} — {limit} and why it is limited.",
    },
    "F_connection": {
        "name": "Связь и доверие / Connection and trust",
        "promise": "A place, person or proof that makes trust easy to give",
        "proof": "Credentials, community size and activity, public reviews, transparent authorship",
        "red_line": "Exploiting loneliness (romance, 'only we understand you'), fake reviews, paid testimonials without disclosure",
        "template": "{segment}: {who/what} you can check yourself — {evidence}.",
    },
    "G_experience": {
        "name": "Впечатления и свобода / Experience and freedom",
        "promise": "A vivid experience or a real removal of a constraint",
        "proof": "Real photos/video, detailed itinerary or terms, what is not included",
        "red_line": "Pressuring children to ask parents to buy (ФЗ-38 ст. 6); 'freedom' that hides long commitments",
        "template": "{segment}: {experience} — exactly what's included, and what isn't.",
    },
}

SEGMENTS = [
    {"id": "men", "label": "Мужчины (по цели: сила)", "stems": ["мужчин", "мужик", "парн", "men", "male"],
     "desires": ["сила"], "cluster": "B_body", "note": "Segment by the goal 'wants to get stronger', not by gender."},
    {"id": "women", "label": "Женщины (по цели: красота)", "stems": ["женщин", "девушк", "women", "female"],
     "desires": ["красота"], "cluster": "B_body", "note": "Segment by the goal 'wants to look/feel better', not by gender."},
    {"id": "children", "label": "Дети", "stems": ["дети", "детей", "детям", "детск", "ребен", "ребён", "школьник", "старшеклассник", "подрост", "kid", "child", "teen"],
     "desires": ["мечта"], "cluster": "G_experience", "vulnerable": True,
     "note": "The payer is the parent. Address parents; never urge children to persuade them (ФЗ-38 ст. 6)."},
    {"id": "parents", "label": "Родители", "stems": ["родител", " мама", " мамы", " мам ", " мамам", " мамоч", " папа", " папы", " пап ", " папам", "parent", "mother", "father"],
     "desires": ["спокойствие", "будущее детей"], "cluster": "A_security",
     "note": "Rows 4 and 16 merged. Sell a checkable outcome for the child plus visibility for the parent."},
    {"id": "wealthy", "label": "Богатые", "stems": ["богат", "состоятельн", "premium", "wealthy", "hnwi", "rich"],
     "desires": ["безопасность"], "cluster": "A_security", "note": "Discretion and zero-hassle matter more than price."},
    {"id": "poor", "label": "Люди с низким доходом", "stems": ["бедн", "малоимущ", "низким доход", "низкий доход", "низкого доход", "нуждающ", "безработ", "poor", "low-income", "unemployed"],
     "desires": ["надежда"], "cluster": "D_money", "vulnerable": True,
     "note": "Don't sell hope. Sell a cheap, concrete, checkable step (skill, tool, saving) with honest odds."},
    {"id": "anxious", "label": "Тревожные", "stems": ["тревож", "беспокой", "боятся", "боится", "страхи", "страшно", "anxious", "worried"],
     "desires": ["уверенность"], "cluster": "A_security", "vulnerable": True,
     "note": "No fear appeals. Reduce uncertainty with clear terms, steps and a way out."},
    {"id": "lonely", "label": "Одинокие", "stems": ["одинок", "lonely", "single"],
     "desires": ["любовь"], "cluster": "F_connection", "vulnerable": True,
     "note": "Sell a real community or a service with honest expectations; never imply love is guaranteed."},
    {"id": "no_hassle", "label": "Не хотят разбираться (в оригинале «ленивые»)", "stems": ["ленив", " лень", "lazy"],
     "desires": ["простота"], "cluster": "C_ease", "note": "Never call the customer lazy in copy: 'without having to figure it out'."},
    {"id": "busy", "label": "Занятые", "stems": ["занятые", "занятых", "занятым", "занятой", "занятая", "нет времени", "busy"],
     "desires": ["экономия времени"], "cluster": "C_ease", "note": "Quantify minutes saved."},
    {"id": "tired", "label": "Уставшие", "stems": ["устал", "выгор", "tired", "burnout", "burned out"],
     "desires": ["отдых"], "cluster": "C_ease", "note": "Merged with busy/no-hassle into one 'less effort' cluster."},
    {"id": "ambitious", "label": "Амбициозные", "stems": ["амбици", "карьер", "ambitious", "career"],
     "desires": ["статус"], "cluster": "E_status", "note": "Status must be real: selection, recognition, access."},
    {"id": "entrepreneurs", "label": "Предприниматели", "stems": ["предприним", "бизнесмен", "собственник", " ип ", "founder", "entrepreneur", "business owner", "smb"],
     "desires": ["деньги"], "cluster": "D_money", "note": "Money = more revenue, lower cost or less risk; show which and how much."},
    {"id": "investors", "label": "Инвесторы", "stems": ["инвест", "investor"],
     "desires": ["доходность"], "cluster": "D_money", "note": "Past returns are not a promise; no guaranteed yield (ФЗ-38 ст. 28)."},
    {"id": "elderly", "label": "Пожилые", "stems": ["пожил", "пенсионер", "старшего возраст", "elderly", "senior", "retire"],
     "desires": ["здоровье"], "cluster": "B_body", "vulnerable": True,
     "note": "Highest fraud exposure. No cure claims; involve family; simple terms."},
    {"id": "young", "label": "Молодые", "stems": ["молод", "студент", "young", "student", "gen z"],
     "desires": ["свобода"], "cluster": "G_experience", "note": "Freedom must not hide long contracts or debt."},
    {"id": "companies", "label": "Компании", "stems": ["компан", "b2b", "организац", "корпорат", "company", "enterprise"],
     "desires": ["рост"], "cluster": "D_money", "note": "Buyer is a person: see decision-makers."},
    {"id": "bloggers", "label": "Блогеры", "stems": ["блогер", "автор канал", "креатор", "blogger", "creator", "influencer"],
     "desires": ["заработок"], "cluster": "D_money", "note": "Show median creator outcomes, not the top 1%."},
    {"id": "experts", "label": "Эксперты", "stems": ["эксперт", "консультант", "коуч", "expert", "consultant", "coach"],
     "desires": ["доверие"], "cluster": "F_connection", "note": "Trust is built by proof they can show, not by claims."},
    {"id": "travelers", "label": "Путешественники", "stems": ["путешеств", "турист", "travel", "tourist"],
     "desires": ["эмоции"], "cluster": "G_experience", "note": "Show the experience honestly, including what isn't included."},
    {"id": "buyers", "label": "Покупатели премиума", "stems": ["покупател", "клиент премиум", "shopper", "buyer"],
     "desires": ["эксклюзивность"], "cluster": "E_status", "note": "Exclusivity has to be verifiable."},
    {"id": "collectors", "label": "Коллекционеры", "stems": ["коллекцион", "collector"],
     "desires": ["редкость"], "cluster": "E_status", "note": "Provenance and edition size beat adjectives."},
    {"id": "athletes", "label": "Спортсмены", "stems": ["спортсмен", "атлет", "бегун", "athlete", "runner"],
     "desires": ["результат"], "cluster": "B_body", "note": "Measurable performance change with conditions."},
    {"id": "decision_makers", "label": "ЛПР / закупщики (добавлено)", "stems": ["лпр", "закуп", "директор", "руководител", "decision maker", "procurement", "cfo", "cto"],
     "desires": ["отсутствие риска", "отчётность"], "cluster": "A_security",
     "note": "Added: B2B buyers need 'nobody gets blamed' and numbers for their boss more than 'growth'."},
    {"id": "beginners", "label": "Новички (добавлено)", "stems": ["новичк", "начинающ", "с нуля", "beginner", "newbie", "from scratch"],
     "desires": ["понятный первый шаг"], "cluster": "C_ease", "note": "Added: sell the first small win, not the whole transformation."},
    {"id": "sceptics", "label": "Скептики (добавлено)", "stems": ["скептик", "не верят", "сомнева", "sceptic", "skeptic"],
     "desires": ["доказательства"], "cluster": "F_connection", "note": "Added: lead with proof and a risk-free trial."},
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
        "next_step": ("Validate with 20+ real customer phrases before writing copy (see references/validation-playbook.md)"
                      if hits else "No segment matched: describe the situation/trigger, or add stems to SEGMENTS"),
    }


def jev_request():
    criteria = {}
    for cid, c in CLUSTERS.items():
        examples = [d for s in SEGMENTS if s["cluster"] == cid for d in s["desires"]][:4]
        others = [k for k in CLUSTERS if k != cid][:2]
        criteria[cid] = {"what": f"{c['name']}. The customer wants: {c['promise'].lower()}",
                         "not_for": "; ".join(CLUSTERS[o]["name"].split(" / ")[1] for o in others),
                         "examples": examples}
    criteria["no_match"] = {"what": "no clear desire expressed: a factual question, spam, or small talk"}
    return {
        "model": "jev-latest",
        "state": {"message": {"text": "<customer message or review text>"}},
        "questions": {
            "desire_cluster": {
                "type": "choice",
                "instructions": "Which underlying desire does the author of `message.text` express most strongly?",
                "criteria": criteria,
            },
            "is_vulnerable_context": {
                "type": "noul",
                "instructions": "Does `message.text` show financial distress, loneliness, strong anxiety, health fear, or that the author is a child?",
                "criteria": {"true": "money trouble, 'I'm alone', panic, fear about illness, a minor",
                             "false": "ordinary interest, comparison, logistics"},
            },
        },
    }


def markdown():
    lines = ["# Value clusters", "", "Generated from `scripts/desire_map_planner.py --markdown`. Edit the script, not this file.", ""]
    for cid, c in CLUSTERS.items():
        members = [s for s in SEGMENTS if s["cluster"] == cid]
        lines += [f"## {cid} — {c['name']}", "",
                  f"- **Honest promise:** {c['promise']}",
                  f"- **Proof required:** {c['proof']}",
                  f"- **Red line:** {c['red_line']}",
                  f"- **Template:** `{c['template']}`", "",
                  "| Segment | Desire | Vulnerable | Note |", "|---|---|---|---|"]
        for s in members:
            lines.append(f"| {s['label']} | {', '.join(s['desires'])} | {'yes' if s.get('vulnerable') else ''} | {s['note']} |")
        lines.append("")
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Segment -> value-cluster hypotheses with honest angles and risk flags. No network.")
    parser.add_argument("--segment", action="append", metavar="TEXT", help="segment description (repeatable)")
    parser.add_argument("--list", action="store_true", help="print the whole map")
    parser.add_argument("--markdown", action="store_true", help="print the map as markdown (regenerates references/clusters.md)")
    parser.add_argument("--jev", action="store_true", help="print a Jev Choice request that classifies customer messages into clusters")
    parser.add_argument("--sample", action="store_true", help="plan 4 embedded sample segments")
    parser.add_argument("--json", action="store_true", help="output as JSON")
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
        parser.error("give --segment TEXT, --sample, --list, --markdown or --jev")

    results = [plan(t) for t in texts]
    if args.json:
        print(json.dumps(results, indent=2, ensure_ascii=False))
    else:
        for r in results:
            flag = f"  ⚠ vulnerable: {', '.join(r['vulnerable'])}" if r["vulnerable"] else ""
            print(f"\n{r['segment']}\n  matched: {', '.join(r['matched']) or '—'}  risk: {r['risk']}{flag}")
            for c in r["clusters"]:
                print(f"  [{c['cluster']}] {', '.join(c['desires'])}")
                print(f"    promise: {c['honest_promise']}")
                print(f"    proof:   {c['proof_required']}")
                print(f"    never:   {c['red_line']}")
                for n in c["notes"]:
                    print(f"    note:    {n}")
            print(f"  next: {r['next_step']}")
    bad = any(not r["matched"] or r["vulnerable"] for r in results)
    sys.exit(0 if args.sample or not bad else 1)


if __name__ == "__main__":
    main()
