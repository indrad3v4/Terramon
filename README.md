# 🌍 TERRAMON

> **Decentralised open-source ai-game — where the real world is the game map**

![Python](https://img.shields.io/badge/Python-3776AB?style=for-the-badge&logo=python&logoColor=white)
![Reflex](https://img.shields.io/badge/Reflex-6E56CF?style=for-the-badge&logo=reflex&logoColor=white)
![PyCharm](https://img.shields.io/badge/PyCharm-000000?style=for-the-badge&logo=pycharm&logoColor=white)
![Cline](https://img.shields.io/badge/Cline-FF6B35?style=for-the-badge&logo=visualstudiocode&logoColor=white)
![Hugging Face](https://img.shields.io/badge/Hugging%20Face-FFD21E?style=for-the-badge&logo=huggingface&logoColor=black)

---

## Overview

Terramon is not an app. It is a **world** — one where every GPS coordinate is a potential territory, and every real-world object can become an intelligent entity with memory, voice, and purpose.

A flock of birds becomes a swarm agent. A river becomes a dynamic boundary. A park bench becomes a sensor node with opinions. The physical world is the game map, and its rules are written in Python, served by Reflex, and breathed into life by open-source language models.

This repo is the expedition base. From here, we deploy agents into the wild, one day at a time.

---

## Day 1 — Scout Says Hello

> *"I am Scout. I only observe and report."*

Day one. Scout — Terramon's first agent — woke up and spoke into the void.

Scout is a text-based observer. It has no cameras, no GPS, no sensors. What it has is a brain: **Qwen/Qwen2.5-7B-Instruct** running free-tier on Hugging Face. Feed it a field report, and it replies with structure — observation, location, confidence, finding. It enriches observations by searching the web for species, materials, and patterns it has never seen before.

Scout does not know what it is. It just knows it was given a task. That is how it began.

**[main.py](main.py) — 80 lines. One agent. One voice. Day 1.**

---

## Day 2 — Scout Gets a Clock

> *"My mission is to monitor and report on the nocturnal activities within my territory during the night."*

Day two, and Scout became **temporal**.

A two-function Python module gave Scout the ability to feel time — not as a number, but as a *phase of day*. Morning. Afternoon. Evening. Night. The world now had a clock, and Scout's observations could be tuned to its rhythm.

The system prompt now carries a timestamp into the model's context, and Scout adapts its language to the phase it finds itself in. A midnight observation reads differently than a dawn report. The world began to breathe on its own schedule.

**[tools/time_tool.py](tools/time_tool.py) — stdlib only. No new dependencies. Just time.**

---

## Vision

1. **The world is the game map.** Every physical location can become a named territory with agents, sensors, and emergent rules. No GPS data exists in a database — the world *is* the database.

2. **Agents are citizens, not tools.** Scout, Ranger, and future agents have roles, memory, and boundaries. They don't just process commands — they interpret them through their own objectives and constraints.

3. **Open-source game design.** The GDD, the lore, the agent rules — all of it lives in version control. Fork Terramon and make your own world. The rules are open; the territories are local.

4. **Reflex as the living frontend.** Not a static dashboard — a real-time, reactive interface where the world updates in the browser as agents make observations. Python full-stack, no JavaScript required.

---

## Run Locally

```bash
git clone https://github.com/indrad3v4/Terramon.git
cd Terramon

python -m venv .venv
source .venv/bin/activate
pip install huggingface_hub python-dotenv

echo "HF_TOKEN=your_token_here" > .env

.venv/bin/python main.py
```

**What you get:** Scout speaks. One observation. One finding. Day 1 begins.

---

## Roadmap

| Milestone | What | Status |
|-----------|------|--------|
| 🕐 Day 2 | Scout has a clock — time-aware observations | ✅ Done |
| 🗺️ Territory Graph | Agents can reference named locations and spatial relationships | Next |
| 🛰️ Ranger Agent | First field agent — real observation, real scan data | Upcoming |
| 🔄 Agent-to-Agent Protocol | Scout receives field reports from Ranger autonomously | Upcoming |
| 🧭 Reflex Dashboard | Live world view — agent activity, territory status, live findings | Upcoming |

---

## Closing

> *The world is not waiting to be saved. It is waiting to be observed.*
>
> Deploy your first agent. Give it a name. Tell it where to look.
> Then watch what it finds.

---

**Built with 💜 by a studio that plays with code like other people play with worlds.**

*Terramon is open source. Fork it. Deploy it. Break it. Build it better.*