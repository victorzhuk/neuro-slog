---
title: a thin identity perimeter for russia
date: 2026-07-03
published: 2026-07-03T13:32:58+03:00
tags: [architecture, compliance, russia]
description: A thin Russian identity node satisfies 152-FZ. СБП and Мир payments are what actually force a Russian entity.
---

You have an EU-hosted product and want to distribute it into Russia. The naive read of the data law says move the backend east. Wrong, and expensive.

The real requirement is narrower: Russian citizens' personal data must be written and mastered in Russia. Nothing else has to move. A small identity node covers it. What actually forces a Russian legal entity is payments -- СБП and Мир, not the data law.

Pattern below: a Telegram Mini App (olympiad math), backend in Lithuania.

Not legal advice. The July 2025 localization edition is still settling in practice -- confirm the final setup with a Russian data-protection lawyer and an accountant.

## Which law matters

149-ФЗ vs 152-ФЗ is the usual confusion. For an EU-hosted consumer app, 152-ФЗ is the one that bites. 149-ФЗ only applies if you host messaging.

| Law | Governs | Applies? |
|---|---|---|
| **152-ФЗ, ч.5 ст.18** | personal-data localization | yes, the main one |
| **149-ФЗ, ст.10.1** | ОРИ registry | only for user-to-user messaging, avoidable |
| **236-ФЗ** | platform "landing" in Russia | from ~500k daily users, not a small app |
| **436-ФЗ** | age rating | trivial, likely 0+/6+ |
| **54-ФЗ** | fiscal receipts, cash registers | only once you take Russian card/СБП payments |

Russian law engages when the product targets Russia: Russian UI, ruble pricing, RuStore distribution, a Russian audience. No entity, no explicit targeting -- a Mini App sits in a grey zone with low enforcement. A standalone RuStore build doesn't: RuStore checks for a Russian entity or ИП at intake.

## What localization requires after July 2025

ч.5 ст.18, updated, effective 1 July 2025: collection, recording, systematization, accumulation, and storage of Russian citizens' personal data must use a database located in Russia. Two things follow: first write lands in Russia, and the Russian database is the authoritative copy. A foreign master with a Russian cache or read replica doesn't satisfy it.

It doesn't ban sending data abroad. Cross-border transfer is a separate basis with its own Roskomnadzor notification (ст.12); for adequate-protection countries the regime is light. Lithuania usually qualifies (EU, Convention 108) -- check the current РКН list, don't assume it.

The rule: first write in Russia, master identity in Russia, transfer abroad as a separate operation.

## The move: a thin identity perimeter

Put a small Russian node in front of the EU backend. It holds `tg_id`, the real name, and the mapping to an internal `user_uuid`. Nothing else. Everything else -- task bank, delivery, progress, scoring, analytics, observability -- stays in the EU and runs on `user_uuid` alone.

```text
   RUSSIA — thin perimeter          │        EU — product brain
                                    │
   Managed Postgres                 │   Go backend
     tg_id, name → user_uuid  ──────┼──►    tasks, progress, scoring
                                    │        analytics, observability
   first PDn write, master copy     │   sees user_uuid only
```

Identity master is Russian. First write lands there. The EU side never sees identity, only the pseudonym. The Go stack doesn't move.

## Staying out of the ОРИ registry

ОРИ duties under 149-ФЗ attach to in-app user-to-user messaging. Don't host it. Keep discussion, comments, chat in Telegram itself. No messages inside your product, no ОРИ classification, none of the registry, retention, or FSB-access duties that follow. For a Mini App living inside Telegram, this costs nothing.

## The leaderboard trap

A leaderboard is a quiet consent landmine. Publishing a real name or Telegram username is distribution of personal data under 152-ФЗ -- its own consent, on top of processing consent. Use self-chosen nicknames (not personal data), keep the `nickname <-> user_uuid` mapping in the EU backend, rank on pseudonyms. Real names never reach the leaderboard. Distribution consent never comes up.

## Payments change everything

Localization fits in a small node. Payments don't. This is where a Russian entity becomes unavoidable.

| | Telegram Stars | СБП + Мир |
|---|---|---|
| seller | Telegram / foreign counterparty | you |
| rails | Fragment / TON | НСПК |
| Russian entity | not required | required: ИП or ООО |
| 54-ФЗ receipt | usually not applicable | mandatory unless an exemption applies |
| downside | TON cash-out, currency-control and tax questions, no native Мир/СБП | full Russian payment and fiscal stack |

Stars: Telegram is the platform and the foreign counterparty. Currency settlement from a foreign counterparty doesn't fall under 54-ФЗ -- same logic as a marketplace issuing receipts for its sellers. You stay foreign, skip the Russian cash register, hold no payment PDn. Cost: funds settle in TON via Fragment, which drags in currency control and tax, and there's no native Мир or СБП.

СБП + Мир: Russian NSPK rails. You can only accept them through a Russian bank or aggregator -- ЮKassa, Т-Банк, CloudPayments -- which needs a Russian ИП or ООО and a settlement account. Then 54-ФЗ applies: cashless payments from individuals online or by QR need an online cash register plus an ОФД, buyer's email or phone on the receipt. СБП has required receipts since 1 March 2025. Miss one and it costs 25-50% of the amount for an ИП (min 10k rub), 75-100% for a legal entity (min 30k rub).

One lever for an education product: since 1 March 2025 an ИП providing educational services can skip the online cash register, and self-employed providers are exempt entirely (receipts via «Мой налог»). Narrow conditions -- confirm with an accountant.

## The fork

Pick the monetization path before building anything else. It decides whether you need a Russian entity at all.

Path A, Stars only: stay foreign. No entity, no cash register, no СБП/Мир. Simplest, legally and operationally. Revenue is Stars-only, cash-out runs through TON.

Path B, СБП/Мир: register in Russia. You're now a Russian operator, taxpayer, probably a cash-register holder. Upside: the Russian perimeter has to exist for billing and fiscalization anyway, so localization comes free with it.

No working СБП without a Russian entity.

## Path B architecture

On Path B the perimeter widens from identity to identity-plus-commerce. Russia gains billing, orders, payment webhooks, fiscalization, receipts, the settlement account. The EU brain is unchanged. Primary PDn collection in Russia is satisfied by the plain fact that billing lives there.

What crosses:

| Stays in Russia | Crosses to EU |
|---|---|
| `tg_id`, real name | `user_uuid` |
| billing, orders, receipts | progress and scores |
| payment PDn (email/phone on the receipt) | `nickname <-> user_uuid` mapping |

Payment data and real names stay in Russia. The EU side gets pseudonyms and learning state.

## Path B checklist

- Russian ИП or ООО, settlement account, aggregator contract
- 54-ФЗ: cash register plus ОФД, unless the education/self-employed exemption applies
- Roskomnadzor processing notification (ст.22) before launch
- cross-border transfer notification (ст.12) -- only pseudonyms cross, exposure is minimal
- processing consent; distribution avoided by design (nicknames)
- no in-app user-to-user messaging (ОРИ)

## What goes wrong if you miss it

At scale: illegal cross-border transfer runs to multi-million-ruble fines. Data leaks are fined heavily, repeat leaks turn turnover-based. A foreign operator with no Russian compliance faces blocking and RuStore removal. Keep personal data out of the cross-border stream and the expensive exposure collapses to near zero.

## Bottom line

152-ФЗ doesn't force the backend east. A thin Russian identity node satisfies localization: first write and master identity in Russia, only pseudonyms to the EU.

Payments decide the entity question. Stars-only, you stay foreign: no entity, no cash register, no fiscalization. Russian card rails, you register -- but the perimeter stays narrow: identity, billing, fiscalization. The product brain and the Go stack stay put.

The server doesn't move. Only the pseudonym travels.
