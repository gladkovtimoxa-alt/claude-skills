# Validating desire hypotheses

The map gives you a guess in seconds. This playbook turns the guess into something you can put money behind in about a week.

## 1. Collect the customers' own words (1-2 days)

Sources, best first:

| Source | What to pull | Minimum |
|---|---|---|
| Sales/support conversations (email, Telegram, chats) | The first message and the "why now" | 30 messages |
| Reviews of you and competitors (Яндекс Карты, 2ГИС, Ozon, Wildberries, Авито, отзовики) | 1-2 star (what failed) and 5 star (what they came for) | 50 reviews |
| Customer interviews | "What was going on when you started looking?" "What did you try before?" "What almost stopped you?" | 5-8 calls |
| Search and marketplace queries (Wordstat, marketplace search hints) | Exact phrasing and volume | top 20 queries |
| Community threads (Telegram chats, VK groups, forums) | Complaints and wishes in their slang | 30 posts |

Copy phrases verbatim. Don't paraphrase — the paraphrase is where your bias sneaks in.

## 2. Classify at scale (1 hour)

- Few dozen phrases → sort by hand into the clusters from `clusters.md`.
- Hundreds → `desire_map_planner.py --jev` prints a ready Jev Choice request; run it per phrase, keep answers with `p(top) ≥ 0.55`, and look at the distribution. Anything with `is_vulnerable_context ≥ 0.6` goes into a separate pile — those people need the careful version of the offer, not the loud one.
- Results you want: top 2 clusters by share, the 10 most typical phrases for each, the triggers ("когда …") that appear most.

## 3. Write the offer, not the slogan

For each of the top 2 clusters fill:

| Field | Question |
|---|---|
| Situation / trigger | When exactly do they start looking? |
| Desired outcome | In their words, what changes? |
| Mechanism | Why does your product produce it? |
| Proof | What can they check before paying? |
| Price and risk reversal | What does it cost, and what happens if it doesn't work? |
| Red line | What you will not promise (from the cluster) |

If you can't fill **Proof** honestly, you don't have an offer for that cluster yet.

## 4. Test cheaply (3-5 days)

- Two to three messages per cluster, same offer, same landing/bot, different angle.
- Channels that give signal in days in Russia: Telegram posts in 3-5 niche channels (посевы), Яндекс Директ search, VK Ads, a message to your own base.
- Measure clicks → leads → first payment, not likes. 100+ clicks per variant before calling a winner (see ab-test-setup for proper sample sizes).
- Every paid placement online needs marking (ERID) — see **ru-marketing-compliance** before launch.

## 5. Decide

| Result | Action |
|---|---|
| One cluster wins on leads *and* first payment | Build the landing, bot answers and FAQ around it |
| Wins on clicks, loses on payment | Promise too big or proof too weak — tighten the offer |
| Nothing works | The segment is wrong, not the words — go back to step 1 with a different situation |
| Vulnerable pile is large | Design a separate, lower-pressure path: plain terms, cooling-off period, human contact |

## Anti-patterns

- Choosing the cluster you like instead of the one the phrases point to.
- Testing slogans without an offer behind them.
- Reading "Одиноким — любовь" and building a funnel on it. Sell a real service with honest expectations; the map tells you what people want, not what you're allowed to promise.
