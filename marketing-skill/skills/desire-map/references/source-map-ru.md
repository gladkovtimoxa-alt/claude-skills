# Source map: «Что продавать людям»

Original list (24 pairs, segment → what to sell), transcribed from a YouTube Shorts video by **@yavkinen**, "Что продавать людям" (screenshots dated 2026-09-21). Kept verbatim so the critique below can point at it.

| # | Кому (segment) | Что продавать (desire) |
|---|---|---|
| 1 | Мужчинам | силу |
| 2 | Женщинам | красоту |
| 3 | Детям | мечту |
| 4 | Родителям | спокойствие |
| 5 | Богатым | безопасность |
| 6 | Бедным | надежду |
| 7 | Тревожным | уверенность |
| 8 | Одиноким | любовь |
| 9 | Ленивым | простоту |
| 10 | Занятым | экономию времени |
| 11 | Амбициозным | статус |
| 12 | Предпринимателям | деньги |
| 13 | Инвесторам | доходность |
| 14 | Пожилым | здоровье |
| 15 | Молодым | свободу |
| 16 | Родителям | будущее детей |
| 17 | Компаниям | рост |
| 18 | Блогерам | заработок |
| 19 | Экспертам | доверие |
| 20 | Путешественникам | эмоции |
| 21 | Покупателям | эксклюзивность |
| 22 | Коллекционерам | редкость |
| 23 | Спортсменам | результат |
| 24 | Уставшим | отдых |

## What's right about it

The core idea is sound and old: people don't buy the product, they buy the change it makes in their life ("sell the hole, not the drill"). A list like this is a fast way to stop describing features and start naming the outcome.

## What's wrong with it (and what the skill does instead)

| # | Problem | Evidence in the list | Fix in this skill |
|---|---|---|---|
| 1 | **Segments mix different axes.** Demographics (men, elderly), roles (investors, bloggers), states of mind (anxious, tired), traits (lazy, ambitious) sit in one column. One person is several at once: a tired, busy entrepreneur-parent. | #1, #7, #9, #12, #16, #24 | Segment by **situation and trigger** (what just happened that makes them look for a solution), then pick the desire. Labels are only search terms. |
| 2 | **Duplicates and overlaps.** Parents appear twice (#4, #16). Lazy / busy / tired (#9, #10, #24) all buy the same thing: less effort. | #4/#16, #9/#10/#24 | Merged into 7 value clusters; duplicates become one segment with two desires. |
| 3 | **Stereotypes.** "Men — strength, women — beauty" excludes most of both groups and can read as sexist in copy. | #1, #2 | Segment by **goal** ("wants to get stronger", "wants to look better"), never by gender alone. |
| 4 | **Vulnerable groups are sold feelings the seller can't deliver.** Hope to the poor, love to the lonely, confidence to the anxious, health to the elderly, dreams to children: the highest-converting and highest-harm promises. | #3, #6, #7, #8, #14 | Flagged `vulnerable`. Sell a concrete, checkable result and let the feeling follow; no fear appeals; legal checks (ФЗ-38 ст. 5, 6, 24, 25, 28) via **ru-marketing-compliance**. |
| 5 | **A desire is not an offer.** "Sell them money" says nothing about mechanism, proof, price, or why you. | all | Every cluster carries: honest promise, required proof, red line, message template. |
| 6 | **It's a guess, not data.** No evidence that *your* customers want this. | all | The map produces hypotheses; the validation playbook checks them against customers' own words and conversion data. |
| 7 | **Missing buyers.** B2B decision-makers, beginners, sceptics, and the user-vs-payer split (parent pays, child uses) aren't there. | — | Added: ЛПР/закупщики → no risk + accountability; новички → a clear first step; скептики → proof; payer ≠ user handled explicitly. |

## Mapping to clusters

| Cluster | Original rows |
|---|---|
| A. Безопасность и спокойствие | 4, 5, 7, 16 |
| B. Тело: здоровье, сила, красота, результат | 1, 2, 14, 23 |
| C. Время и простота | 9, 10, 24 |
| D. Деньги и рост | 6, 12, 13, 17, 18 |
| E. Статус и уникальность | 11, 21, 22 |
| F. Связь и доверие | 8, 19 |
| G. Впечатления и свобода | 3, 15, 20 |

Full cluster definitions (promise, proof, red line, template) live in `scripts/desire_map_planner.py` (`--list`) and in [clusters.md](clusters.md).
