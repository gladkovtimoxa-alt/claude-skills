# Russian advertising law — working summary for marketers

**Not legal advice.** A practitioner's map of the rules that most often break campaigns, written from the law as known in mid-2026. Before a launch with real money or a regulated category, check the current text (КонсультантПлюс / Гарант / pravo.gov.ru) and ФАС practice. Items marked 🟡 change often — verify them every time.

## ФЗ-38 «О рекламе» (13.03.2006) — the articles that matter

| Article | Rule | Typical violation |
|---|---|---|
| **ст. 5** — general requirements | Advertising must be fair (добросовестная) and truthful (достоверная). No false claims about advantages, properties, price, guarantees; no omission of essential conditions (ч. 7). | «Лучший», «№1», «самый» without an objective, sourced criterion; «бесплатно» hiding a subscription; guaranteed results. |
| **ст. 6** — minors | No urging children to persuade parents to buy; no suggesting they're inferior without the product; no discrediting parents or teachers. | «Попроси маму купить», «у всех одноклассников уже есть». |
| **ст. 7** — banned goods | Goods that can't be sold or need a licence you don't have can't be advertised. | Unlicensed financial/medical services. |
| **ст. 18** — distribution by phone/SMS/email/messengers | Only with the recipient's **prior consent**; the distributor must prove it and stop on request. | Mass Telegram/WhatsApp/SMS blasts to bought or scraped bases. |
| **ст. 18.1** — online ad marking | Since 01.09.2022 every online ad: label «Реклама», advertiser info (name/ИНН or a link to it), and an **erid** token obtained via an ОРД; data reported to ЕРИР (Роскомнадзор). | Telegram посевы and blogger integrations without erid; reposted creatives with a stale token. |
| **ст. 24** — medicines, medical services and devices | Mandatory warning about contraindications and consulting a specialist (not less than 5% of the ad's area/time). | Clinic ads without the warning; cure promises. |
| **ст. 25** — БАД | «Не является лекарственным средством»; no creating the impression it's a medicine or that it cures. | «Вылечит суставы», «замена таблеткам». |
| **ст. 28** — financial services | Name of the provider; no guaranteeing returns or future effectiveness of investments; key terms can't be hidden. | «Доходность 30% гарантирована», trading courses promising income. |

Other areas with their own articles (alcohol, tobacco, gambling, weapons, credit, crypto) — read the specific article before touching them.

## Where online ads are banned 🟡

Since 01.09.2024 placing ads on resources of organisations whose activity is banned in Russia (Instagram, Facebook) and on resources of иноагенты is prohibited, and so is advertising with them. Buying placements from such bloggers or on those platforms for the Russian audience is the fastest way to a fine.

## Marking workflow (ОРД → erid)

1. Contract with the placement (or a direct deal) → register the contract with an ОРД (e.g. through the ad platform's own ОРД for Яндекс/VK, or an independent ОРД for Telegram посевы and bloggers).
2. Register each creative → get **erid**.
3. Publish with «Реклама», advertiser info and erid (in the text or the link: `?erid=...`).
4. Report acts and statistics to the ОРД monthly (the ОРД passes them to ЕРИР).
5. New creative text = new erid. Don't copy an old token to a new post.

Self-promotion in your own channel about your own goods is generally not treated as advertising requiring marking; paid placements elsewhere are. Grey cases (barter, affiliate links, UGC with payment) — assume marking is needed. 🟡

## Money and fees 🟡

- Fines for advertising violations are under **КоАП ст. 14.3** (for legal entities up to hundreds of thousands of rubles per violation); marking violations have their own fines. Check current amounts.
- Since 2025 platforms/advertisers pay a mandatory **3% levy** on online advertising revenue — affects pricing of placements. Check who pays in your chain.

## Personal data (152-ФЗ) for leads and messaging 🟡

- Collecting phone/email/Telegram handles for marketing needs consent to personal-data processing with a clear purpose.
- Consent to process personal data must be a **separate** document/checkbox, not buried in the offer or privacy policy (in force since 01.09.2025 — verify details).
- Marketing messages (ст. 18 ФЗ-38) need their own prior consent to receive advertising. Two different consents; log both with timestamps.
- Store data of Russian users in Russia (localisation) and register as an operator with Роскомнадзор where required.

## Consumer protection (ЗоЗПП) touchpoints

- Distance selling: the customer can return goods of proper quality within 7 days (with exceptions); information about the seller, price and terms must be available before purchase.
- For online courses (информационные услуги) the customer can generally cancel and get money back minus actually incurred costs — "no refunds" clauses don't hold up. Put the real refund policy in the offer.

## Quick pre-launch checklist

- [ ] Every claim of superiority has a source and a criterion.
- [ ] No guaranteed outcomes, income, cures.
- [ ] Mandatory disclaimers for the category (medicine / БАД / finance).
- [ ] Nothing addresses children to pressure parents.
- [ ] Online: «Реклама» + advertiser + erid; contract and creative registered in an ОРД.
- [ ] Not placed on banned platforms or with иноагенты.
- [ ] Mailing base: separate consents for personal data and for advertising, logged.
- [ ] Refund terms stated and legal.

`scripts/ad_claim_checker.py` automates the text part of this list.
