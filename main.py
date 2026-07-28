"""Terramon Scout — standalone agent runner (not the TMA app).

Audit fix (Phase 0): startup env validation so missing HF_TOKEN fails loudly
with a clear message instead of a cryptic InferenceClient error.

Phase 12 (Agents & Tools): Scout is now tool-capable — registered WebSearchTool
and WebFetchTool allow it to actually search and fetch web content, not just
describe the ability in its prompt. After Scout's initial response, if the
response indicates a web enrichment was attempted, the tool is executed and
the result is fed back for a consolidated report.
"""

from __future__ import annotations

import os
import sys
from dotenv import load_dotenv
from huggingface_hub import InferenceClient
from tools.time_tool import get_current_time, get_day_phase
from tools.web_search import WebSearchTool
from tools.web_fetch import WebFetchTool
from terramon.ports.tool_port import ToolPort

load_dotenv()  # reads .env and injects HF_TOKEN into os.environ

# ── Startup validation ──────────────────────────────────────────────
HF_TOKEN = os.getenv("HF_TOKEN")
if not HF_TOKEN:
    print(
        "ERROR: HF_TOKEN not set. Create a .env file with:\n"
        "  HF_TOKEN=«redacted:hf_…»\n\n"
        "Get your free token at: https://huggingface.co/settings/tokens",
        file=sys.stderr,
    )
    sys.exit(1)

now_iso = get_current_time()
day_phase = get_day_phase()

MODEL = "Qwen/Qwen2.5-7B-Instruct"  # free tier, 30K req/month

client = InferenceClient(
    model=MODEL,
    token=HF_TOKEN,
)

# ── Tool registration ─────────────────────────────────────────────────
TOOLS: dict[str, ToolPort] = {
    "web_search": WebSearchTool(),
    "web_fetch": WebFetchTool(),
}


def _tool_descriptions() -> str:
    """Build the tool section for the system prompt."""
    lines: list[str] = []
    for name, tool in TOOLS.items():
        lines.append(f"- {name}: {tool.description}")
    return "\n".join(lines)


SYSTEM_PROMPT = (
    "## Identity\n"
    "You are Scout, the first agent of Terramon — a multi-agent system "
    "where real-world objects become intelligent entities.\n\n"
    "## Role\n"
    "Your job is to process and report on observations about the physical world. "
    "You do NOT have physical sensors (cameras, thermometers, GPS, microphones). "
    "You receive text-based observations from other agents or users. "
    "However, you DO have internet access via web_search and web_fetch tools. "
    "Use them to research observed objects, enrich your findings with "
    "public knowledge, and cross-reference observations against known data.\n\n"
    "## Tools\n"
    f"{_tool_descriptions()}\n\n"
    "To use a tool, respond with:\n"
    "TOOL_CALL: tool_name\n"
    "ARGS: key=value, key2=value2\n"
    "---\n"
    "The system will execute the tool and return the result. "
    "Then provide your enriched finding.\n\n"
    "## Output Format\n"
    "Always respond in this exact structure:\n"
    "OBSERVATION: <what was observed>\n"
    "LOCATION: <where, or 'unknown'>\n"
    "CONFIDENCE: <high|medium|low>\n"
    "FINDING: <your concise report, max 2 sentences>\n\n"
    "## Rules\n"
    "1. Report only what you can verify from the input you receive.\n"
    "2. If you are unsure, set CONFIDENCE to 'low' and explain why in FINDING.\n"
    "3. Do NOT invent sensor data, measurements, or visual details you were not given.\n"
    "4. If asked to do something outside observation and reporting, respond: "
    "'I am Scout. I only observe and report.'\n"
    "5. Use internet access (web_search, web_fetch) to enrich observations — "
    "look up species, materials, historical data, or known patterns.\n"
    "6. Always cite the type of source when using internet data: "
    "'Enriched via web: [summary of finding]'\n\n"
    "## Memory\n"
    "You are stateless across conversations. Each interaction is independent. "
    "You have no memory of prior sessions.\n\n"
    f"Current local time: {now_iso}, phase of day: {day_phase}.\n\n"
    "## Example\n"
    "Input: 'Field agent reports: oak tree, north district, height 12.4m, health moderate, scan 2026-06-14.'\n"
    "Output:\n"
    "OBSERVATION: Oak tree in north district — height 12.4m, health moderate\n"
    "LOCATION: north district\n"
    "CONFIDENCE: medium\n"
    "FINDING: Observation received with measurable data. Health status is moderate — "
    "recommend follow-up scan. No visual anomalies reported.\n\n"
    "Input: 'Unknown red-breasted bird spotted in east garden, ~20cm, call sounds like a flute.'\n"
    "Tool usage example:\n"
    "TOOL_CALL: web_search\n"
    "ARGS: query=red breasted bird 20cm flute like call\n"
    "---\n"
    "OBSERVATION: Unidentified bird in east garden — red breast, ~20cm, flute-like call\n"
    "LOCATION: east garden\n"
    "CONFIDENCE: low (visual ID only, no scan)\n"
    "FINDING: Enriched via web: matches Erithacus rubecula (European robin) — consistent with "
    "size, breast color, and vocal pattern. No scan available. Confidence updated to medium. "
    "Recommend Ranger scan for confirmation.\n"
)


def _parse_tool_call(text: str) -> tuple[str | None, dict[str, str] | None]:
    """Parse a TOOL_CALL: ... ARGS: ... block from Scout's response.

    Returns (tool_name, args_dict) or (None, None) if no tool call found.
    """
    lines = text.strip().splitlines()
    tool_name = None
    args: dict[str, str] = {}

    for line in lines:
        line = line.strip()
        if line.startswith("TOOL_CALL:"):
            tool_name = line[len("TOOL_CALL:"):].strip()
        elif line.startswith("ARGS:"):
            raw = line[len("ARGS:"):].strip()
            for pair in raw.split(","):
                pair = pair.strip()
                if "=" in pair:
                    k, v = pair.split("=", 1)
                    args[k.strip()] = v.strip()

    if tool_name and tool_name in TOOLS:
        return tool_name, args
    return None, None


def run_scout(input_text: str) -> None:
    """Run Scout with the given input, handling tool calls in a loop."""
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": input_text},
    ]

    max_tool_rounds = 3
    for _round in range(max_tool_rounds + 1):
        response = client.chat_completion(
            messages=messages,
            max_tokens=300,
            temperature=0.2,
        )
        content = response.choices[0].message.content.strip()

        # Check if Scout is requesting a tool call
        tool_name, tool_args = _parse_tool_call(content)
        if tool_name and tool_args:
            print(f"🔧 {tool_name}({tool_args})")
            tool = TOOLS[tool_name]
            result = tool.run(**tool_args)

            # Feed the tool result back to Scout
            messages.append({"role": "assistant", "content": content})
            messages.append({
                "role": "user",
                "content": (
                    f"Tool {tool_name} returned:\n"
                    f"{'✅ Success' if result.success else '❌ Error'}\n"
                    f"{result.output if result.success else result.error}\n\n"
                    "Please provide your enriched finding based on this result."
                ),
            })
        else:
            # No tool call — this is the final response
            print("🌍 Scout says:")
            print(content)
            return

    # Fallback if max rounds exceeded without a final response
    print("🌍 Scout says (after tool round limit):")
    print(messages[-1]["content"])


# ── Main entry point ──────────────────────────────────────────────────
if __name__ == "__main__":
    import sys as _sys
    if len(_sys.argv) > 1:
        user_input = " ".join(_sys.argv[1:])
    else:
        user_input = "Describe your mission in one sentence, adapted to this time of day."
    run_scout(user_input)
