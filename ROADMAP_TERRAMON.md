# Terramon × AI Engineering — Build Via Learn Roadmap

> Generated 2026-07-18.
> Left column: course phase from `ai-engineering-from-scratch` (cloned locally). Right: where it lands in Terramon.
> Principle (your LEARNING_PATH.md): *Learning = doing. Doing = Terramon.*

## How a course lesson becomes a Terramon step

```
Course lesson N  ──read/derive──▶  write the pattern in terramon/ (port|adapter|domain)
        │                                     │
        │                                     ▼
        └─── proves understanding ──▶  pytest test in tests/ (offline)
```

Every Terramon step below has a real file already created in this session (see Payment layer).

## Phase-by-phase mapping

| Course Phase | Terramon build step | Why it lands there | Lessons |
|:---:|---|---|:---:|
| **1** Math Foundations | Background — read before forking LLM code | Needed to READ attention/backprop you'll reuse | 22 |
| **2** ML Fundamentals | Background for classifier quality | Revisit when tuning Fireworks intent model | 18 |
| **3** Deep Learning Core | PyTorch fluency pre-AMD fine-tune | Backprop before GPU classifier | 13 |
| **5** NLP | Tokenization + embeddings feed classifier | Day 8 Fireworks intent routing | 29 |
| **7** Transformers Deep Dive | Understand what Fireworks returns | Self-attention from scratch = capstone | 16 |
| **10** LLMs from Scratch | Day 8 Fireworks classifier = applied P10 | Mini-GPT logic for creature lore gen | 24 |
| **11** LLM Engineering | RAG + guardrails + cost | Creature memory retrieval + prompt-injection defense | 17 |
| **13** Tools & Protocols | **PaymentPort is literally P13** | MCP servers -> creature tools. Directly applied | 23 |
| **14** Agent Engineering | Multi-agent world (Day 13) + payment gate | Verification gate = P14 pattern | 42 |
| **17** Infrastructure & Production | AMD GPU deploy, Docker, vLLM, observability | Hackathon submit + S17 perf | 28 |
| **18** Ethics, Safety & Alignment | Prompt-injection defense on summon input | P18 applied to game security | 30 |
| **19** Capstone Projects | Terramon IS a capstone | Use P19 deep-build tracks (agent harness, RAG, dist) | 85 |

## What's built so far (this session)

| File | Role | Course link |
|---|---|---|
| `terramon/ports/payment_port.py` | `PaymentPort` Protocol (onchain/lightning/stripe) | P13 Tools & Protocols |
| `terramon/adapters/onchain_adapter.py` | BTC on-chain, watch-only, treasury `bc1q…` | P13 + P17 |
| `terramon/adapters/lightning_adapter.py` | LNBits BOLT11 invoices | P13 + Day 14 |
| `terramon/adapters/stripe_adapter.py` | EUR subscription (fiat, not BTC) | P13 + Slide 6 |
| `terramon/domain/rarity.py` | rarity tiers + sats pricing (Day 59) | P11 economy |
| `terramon/application/payment_gate.py` | verification gate | P14 verification gates |
| `terramon/application/summon_service.py` | summon + `summon_paid()` | P10/P14 |
| `tests/test_payment.py` | 14 offline tests, all green | — |

**Test result:** `python -m pytest tests/ -q` → 17 passed (3 original + 14 new).

## Next 10 Terramon steps (build via learn)

| Step | What | Course anchor |
|:---:|---|---|
| S0.2 | Wire real Blockstream lookup in OnChainAdapter (remove fake) — verify a real tx to bc1q… | P17 / Day 14 |
| S0.3 | LNBits creds via .env (LNBITS_URL, LNBITS_API_KEY); first live Lightning invoice | P13 / Day 14 |
| S0.4 | Stripe Checkout session for SUMMONER €9.99 (test mode key) | P13 / Slide 6 |
| S1 | Schell Lens #1 on the summon+pay loop (Essential Experience) | LEARNING_PATH |
| S2 | Fireworks classifier adapter = ClassifierPort (replace keyword) | P10 / Day 8 |
| S3 | Creature tool use as MCP servers (Phase 13 deep) | P13 |
| S4 | Prompt-injection defense on summon input | P18 |
| S5 | Multi-agent world events (agent-to-agent) | P14 / Day 13 |
| S6 | AMD GPU deploy + Docker (hackathon submit) | P17 |
| S7 | RAG over thought-seed memory for creature responses | P11 / P19 |

## Money flow (as built)

```
thought seed --(rarity)--> common/uncommon = FREE
                         \-> rare/legendary = PAID
                              ├─ OnChainAdapter  -> bc1q5am… (watch-only, live tx verify)
                              ├─ LightningAdapter -> LNBits BOLT11 (instant sats)
                              └─ StripeAdapter   -> EUR subscription (NOT bitcoin)
```

> NOTE: `bc1q…` is a PUBLIC receiving address — safe to publish. Private key never touched.
> Stripe does not settle BTC; it is the fiat (EUR) rail only.
