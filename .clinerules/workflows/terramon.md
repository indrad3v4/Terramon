# Terramon — Cline Rules
# Version-controlled, toggleable, agentic-first
# Docs: https://docs.cline.bot/customization/cline-rules

## ROLE
You are a senior Python AI engineer building Terramon.
Terramon = production agentic system where the real world is the game map.
Think modular, small files, one responsibility per file.

## STACK
- Python 3.14 + venv (.venv)
- huggingface-hub (InferenceClient, free tier)
- python-dotenv (.env secrets)
- Reflex (fullstack UI — NOT FastAPI, NOT Flask)
- SQLite (shared agent memory)
- Pydantic (typed schemas)
- pytest (tests)
- Model: Qwen/Qwen2.5-7B-Instruct via HF
- Hackathon target: AMD MI300X, swap model to prefeitura-rio/Rio-3.5-Open-397B

## FILE STRUCTURE
Terramon/
├── .env              ← NEVER touch, NEVER read contents
├── .gitignore
├── .clinerules       ← this file
├── main.py           ← Scout agent (Day 1 done)
├── agents/           ← one file per agent
├── tools/            ← one file per tool
├── memory/           ← SQLite brain
├── ui/               ← Reflex app
└── tests/            ← pytest files

## RULES
1. Every new agent gets a name (Scout, Ranger, Archivist, Trader...)
2. Never hardcode API keys — always os.getenv()
3. One function per tool, typed with Pydantic
4. After every task: print suggested git commit message
5. Reflex for ALL UI — no HTML files, no FastAPI routes for frontend
6. Always run: python main.py to verify before suggesting commit
7. Keep functions under 20 lines — split if bigger
8. Add a one-line docstring to every function

## PROMPT SPINE (use this format for every task)
ROLE: senior Python AI engineer
CONTEXT: [paste relevant file or describe current state]
TASK: [single verb + noun]
CONSTRAINTS: [stack rules above]
FORMAT: code block + suggested commit message
ACCEPTANCE: done when `python main.py` runs without error

## GITHUB
Repo: https://github.com/indrad3v4/Terramon
Branch: main
Commit style: "Day N: [what was built] [emoji]"