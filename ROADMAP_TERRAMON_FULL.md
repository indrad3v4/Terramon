# Terramon × AI Engineering — FULL 20-Phase Build-Via-Learn Map

> Generated 2026-07-18. ALL 20 phases (0 → XIX) mapped to concrete Terramon build steps.
> Source of truth: cloned `ai-engineering-from-scratch` (README.md) + `Terramon` repo.
> Principle (LEARNING_PATH.md): *Learning = doing. Doing = Terramon. Terramon = portfolio.*
>
> **This is a TRACKING MAP, not 503 lessons of code in one pass.** Each phase lists
> the Terramon step(s) it unlocks. We build them in order, lesson-by-lesson, applying
> the course concept to game code and proving it with a test.

## Legend
- ✅ already built this session
- 🔜 next up
- ⬜ planned (build when we reach that phase)

## Phase overview (all 20)

| # | Course Phase | Terramon role | Built |
|:---:|---|---|:---:|
| 0 | Setup & Tooling | Dev env, venv, pytest, CI | ✅ (verify 7/7) |
| 1 | Math Foundations | Vector/matrix utilities for agent state, embeddings math | ⬜ |
| 2 | ML Fundamentals | Intent classifier quality, feature engineering for rarity | ⬜ |
| 3 | Deep Learning Core | PyTorch fluency before AMD fine-tune | ⬜ |
| 4 | Computer Vision | Ranger agent: image/scene understanding | ⬜ |
| 5 | NLP | Tokenization + embeddings for Fireworks classifier | ⬜ |
| 6 | Speech & Audio | Voice summon (Whisper), TTS creature voices | ⬜ |
| 7 | Transformers Deep Dive | Understand Fireworks output; self-attention from scratch | ⬜ |
| 8 | Generative AI | Creature art (diffusion), lore image gen | ⬜ |
| 9 | Reinforcement Learning | Agent self-improvement, reward modeling | ⬜ |
| 10 | LLMs from Scratch | Fireworks classifier = applied P10; creature lore gen | 🔜 (S2) |
| 11 | LLM Engineering | RAG over memory, guardrails, cost (payment gating) | ⬜ |
| 12 | Multimodal AI | VLM creatures, vision-language summon | ⬜ |
| 13 | Tools & Protocols | **PaymentPort ✅**, MCP servers = creature tools | ✅ |
| 14 | Agent Engineering | Multi-agent world (Day 13), payment gate = verification gate | ⬜ |
| 15 | Autonomous Systems | Long-horizon agent loops, safety stack | ⬜ |
| 16 | Multi-Agent & Swarms | Agent societies, debate, coordination | ⬜ |
| 17 | Infrastructure & Production | AMD GPU deploy, Docker, vLLM, observability | ⬜ |
| 18 | Ethics, Safety & Alignment | Prompt-injection defense on summon input | ⬜ |
| 19 | Capstone Projects | **Terramon IS the capstone** — use deep-build tracks | 🔁 |

---

## Phase 0 — Setup & Tooling ✅ DONE
- [x] `uv` 0.11.29 installed (lesson 1)
- [x] Python 3.13.5 + numpy/matplotlib/jupyter (.venv-course)
- [x] Node 22.23.1 + pnpm 11.14.0
- [x] Rust 1.97.1 (cargo)
- [x] PATH persisted in ~/.profile
- [x] verify.py → 7/7 core passed
- [x] Terramon: `.venv` + pytest, 17 tests green
- **Next:** keep env reproducible; add `requirements.lock` via uv

## Phase 1 — Math Foundations ⬜
Build steps in Terramon:
- [ ] `terramon/math/vectors.py` — vector ops used by agent position/territory state
- [ ] Gradient/derivative helper for rarity scoring tuning
- [ ] Lesson proof: unit-test vector dot product against numpy
- Course lessons: 22 (Linear Algebra Intuition → Fourier Transform)

## Phase 2 — ML Fundamentals ⬜
- [ ] Improve `KeywordClassifier` → feature-based scoring (TF-IDF lite)
- [ ] Rarity model as a trained classifier (not hardcoded patterns)
- [ ] Cross-validation harness for intent accuracy
- Course lessons: 18

## Phase 3 — Deep Learning Core ⬜
- [ ] `terramon/adapters/pytorch_classifier.py` scaffold (ClassifierPort)
- [ ] Mini framework understanding before AMD fine-tune
- [ ] Backprop from scratch → later transfer to creature behavior nets
- Course lessons: 13

## Phase 4 — Computer Vision ⬜
- [ ] Ranger agent: image captioning via HF/Vision model
- [ ] Territory map rendering from camera input
- [ ] Convolutions from scratch (lesson 2) proven with test
- Course lessons: 28

## Phase 5 — NLP ⬜
- [ ] Subword tokenization for thought seeds (BPE from scratch, lesson 19)
- [ ] Embeddings for semantic memory recall (replaces JSONL keyword search)
- [ ] Feeds Fireworks classifier (Day 8)
- Course lessons: 29

## Phase 6 — Speech & Audio ⬜
- [ ] Voice summon: Whisper STT → thought seed
- [ ] TTS creature voices (Day 3 roadmap)
- [ ] Audio eval (WER) for summon accuracy
- Course lessons: 17

## Phase 7 — Transformers Deep Dive ⬜
- [ ] Self-attention from scratch (lesson 2) → understand Fireworks returns
- [ ] Build a transformer capstone (lesson 14) reused for lore generation
- [ ] KV cache / Flash Attention notes for inference speed
- Course lessons: 16

## Phase 8 — Generative AI ⬜
- [ ] Creature art: diffusion/Stable Diffusion for summoned portraits
- [ ] Latent diffusion pipeline for territory maps
- [ ] Evaluation: FID/CLIP score for creature art
- Course lessons: 15 (+19 VAR)

## Phase 9 — Reinforcement Learning ⬜
- [ ] Agent reward modeling: creatures learn from player feedback
- [ ] PPO/DPO for creature personality tuning
- [ ] RLHF applied to classifier (links to P10)
- Course lessons: 12

## Phase 10 — LLMs from Scratch 🔜 S2
- [ ] **S2: Fireworks classifier adapter = ClassifierPort** (replace keyword)
- [ ] Tokenizer from scratch (lesson 2) → creature name generator
- [ ] Pre-training Mini-GPT logic for lore generation (lesson 4)
- [ ] Quantization for edge summon (lesson 11)
- Course lessons: 24 (+25/34 extras)

## Phase 11 — LLM Engineering ⬜
- [ ] RAG over thought-seed memory (lesson 6) → creature recalls past
- [ ] Structured outputs for summon JSON (lesson 3)
- [ ] Guardrails + cost (lesson 12) → **PaymentPort gating already built**
- [ ] Eval harness for summon quality
- Course lessons: 17

## Phase 12 — Multimodal AI ⬜
- [ ] VLM creatures: vision + language summon (lesson 5 LLaVA)
- [ ] ColPali document RAG for codex lore
- [ ] Multimodal agents / computer-use capstone
- Course lessons: 25

## Phase 13 — Tools & Protocols ✅ BUILT
- [x] `PaymentPort` (onchain/lightning/stripe)
- [x] `OnChainAdapter` (bc1q… watch-only)
- [x] `LightningAdapter` (LNBits)
- [x] `StripeAdapter` (EUR)
- [ ] **Next:** creature tools as MCP servers (lesson 7, 13, 22)
- [ ] A2A protocol for agent-to-agent tool calls
- Course lessons: 23

## Phase 14 — Agent Engineering ⬜
- [ ] Multi-agent world (Day 13): agent-to-agent events
- [ ] **PaymentGate = verification gate (already built, P14 pattern)**
- [ ] Memory blocks (Mem0-style) for creature long-term state
- [ ] Orchestration: supervisor/swarm patterns
- [ ] Agent workbench for Terramon dev
- Course lessons: 42

## Phase 15 — Autonomous Systems ⬜
- [ ] Long-horizon agent loops (METR)
- [ ] Self-improvement: creature evolves with use
- [ ] Safety stack: kill switches, cost governors on summon
- Course lessons: 22

## Phase 16 — Multi-Agent & Swarms ⬜
- [ ] Agent societies: debate/coordination between creatures
- [ ] Role specialization (Planner/Critic/Executor)
- [ ] Swarm optimization for territory control
- [ ] MARL for creature conflict
- Course lessons: 25

## Phase 17 — Infrastructure & Production ⬜
- [ ] AMD GPU deploy + Docker (hackathon submit, Day 16)
- [ ] vLLM serving for Fireworks-classifier replacement
- [ ] Observability (OTel, Langfuse) for summon pipeline
- [ ] FinOps: cost per summon tracked via PaymentPort
- Course lessons: 28

## Phase 18 — Ethics, Safety & Alignment ⬜
- [ ] **Prompt-injection defense on summon input** (P18 applied)
- [ ] Red-team the classifier (lessons 12, 14, 15)
- [ ] Watermarking creature art (lesson 23)
- [ ] Alignment: creatures stay helpful, not deceptive
- Course lessons: 30

## Phase 19 — Capstone Projects 🔁
Terramon is itself the capstone. Use P19 deep-build tracks:
- [ ] Agent harness loop contract (track A) → Terramon summon loop
- [ ] NLP/LLM track (B) → tokenizer + GPT assembly for lore
- [ ] Distributed train (C/H) → if we self-host classifier
- [ ] Advanced RAG (F) → memory recall
- [ ] Eval framework (G) → summon quality gates
- [ ] Safety harness (I) → prompt-injection + refusal
- Course lessons: 85 (17 projects + 9 deep-build tracks)

---

## How we execute (the loop)
```
1. Pick next phase in order (currently: Phase 1, since 0 + 13 done)
2. Read lesson N from cloned course
3. Build the matching Terramon step (port/adapter/domain/service)
4. Prove with a pytest test (offline, injectable I/O)
5. Mark [x] here, commit to Terramon (squash to main)
6. Next lesson
```

## Money already wired (so the startup returns $)
```
thought seed → rarity → common/uncommon = FREE
                         → rare/legendary = PAID
                              ├─ OnChainAdapter  → bc1q5am… (live tx verify)
                              ├─ LightningAdapter → LNBits BOLT11 (sats)
                              └─ StripeAdapter   → EUR subscription (fiat)
```

> Status 2026-07-18: Phase 0 ✅, Phase 13 ✅ (PaymentPort merged to main).
> 18 phases remain. Build order: 1 → 2 → 3 → 4 → 5 → 6 → 7 → 8 → 9 → 10 → 11 → 12 → 14 → 15 → 16 → 17 → 18 → 19.
