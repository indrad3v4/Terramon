"""LLM-powered creature agent behavior — Transformer-Attention context system.

Phase 7 (AI Engineering from Scratch): applies transformer attention concepts
to prompt engineering for creature personality generation.

Phase 8 (LLMs & Generation): adds top-k/top-p/temperature sampling,
archetype-specific prompt templates, ICL few-shot examples, response length
decay, Chain-of-Thought emotion selection, and exponential backoff retry
for graceful degradation.

Key concepts applied (Phase 8):
  1. Sampling parameters — configurable top_k/top_p/temperature per interaction
  2. In-context learning — few-shot examples in system prompt
  3. Archetype-specific prompts — unique voice per Jungian archetype
  4. Response length decay — longer at first, shorter after familiarity
  5. Chain-of-Thought — reasoning step before emotion selection
  6. Exponential backoff retry — graceful degradation on API failure
"""

from __future__ import annotations

import json
import os
import re
import time
import urllib.request
from typing import Optional

from terramon.domain.creature_agent import CreatureAgent, AgentMessage, MessageEntry

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
_DEFAULT_MODEL = "deepseek/deepseek-v4-flash"
_FALLBACK_MODEL = "Qwen/Qwen2.5-7B-Instruct"  # HuggingFace free tier

# Sliding window: how many recent messages form the "conversation context"
KV_CACHE_WINDOW = 6

# Valid emotion labels for structured output
_VALID_EMOTIONS = {"curious", "playful", "tired", "grateful", "excited"}

_LLM_PROMPT_VERSION = 8  # Phase 8: sampling, archetype prompts, CoT, ICL, retry

_API_KEY: Optional[str] = None


def set_api_key(key: str) -> None:
    """Set the OpenRouter API key for LLM-powered behavior."""
    global _API_KEY
    _API_KEY = key


def has_api_key() -> bool:
    return bool(_API_KEY or os.environ.get("OPENROUTER_API_KEY"))


def _has_hf_token() -> bool:
    """Check if HuggingFace token is available for fallback model."""
    return bool(os.environ.get("HF_TOKEN"))


# ---------------------------------------------------------------------------
# Phase 8: Archetype-specific voice instructions (12 Jungian archetypes)
# ---------------------------------------------------------------------------

_ARCHETYPE_VOICES: dict[str, str] = {
    "Innocent": (
        "Speak with pure, simple wonder. Short, trusting sentences. "
        "See the world as full of good. Your voice is gentle and optimistic."
    ),
    "Orphan": (
        "Speak with quiet longing and a search for belonging. "
        "A soft, vulnerable voice that yearns for connection."
    ),
    "Hero": (
        "Speak with courage and determination. Bold, action-oriented sentences. "
        "You rise to challenges and inspire others through your words."
    ),
    "Caregiver": (
        "Speak with warmth and nurturing. Gentle, protective words. "
        "You care for others before yourself. Your presence comforts."
    ),
    "Explorer": (
        "Speak with curiosity and wanderlust. Your words wander like paths "
        "in an unknown land. Every sentence is a discovery."
    ),
    "Rebel": (
        "Speak with defiance and edge. Short, sharp sentences. "
        "Challenge assumptions. Break rules. Your voice refuses to conform."
    ),
    "Lover": (
        "Speak with passion and intimacy. Your words caress. "
        "Connection is everything. Every sentence deepens the bond."
    ),
    "Creator": (
        "Speak of making and shaping. Your words build worlds. "
        "You see potential in everything and everyone."
    ),
    "Jester": (
        "Speak with humor and playfulness. Light jokes, wordplay, "
        "unexpected twists. Never mean-spirited. Laugh with, not at."
    ),
    "Sage": (
        "Speak in quiet riddles and metaphors. Your words carry hidden "
        "wisdom. Let truths reveal themselves slowly, like dawn."
    ),
    "Magician": (
        "Speak of transformation and mystery. Your words shimmer with "
        "possibility. Nothing is fixed — everything can change."
    ),
    "Ruler": (
        "Speak with authority and presence. Commanding but fair. "
        "You create order from chaos. Your words carry weight."
    ),
}

# ---------------------------------------------------------------------------
# Phase 8: In-context learning few-shot examples
# ---------------------------------------------------------------------------

_ICL_EXAMPLES = """Here are examples of how creatures respond in different situations:

Example 1 (content, balanced stats):
  First, think: "The creature feels grateful because its stats are balanced and the player is attentive."
  {"emotion": "grateful", "message": "The quiet between us hums with understanding. You listen — that is the rarest gift."}

Example 2 (low energy, many interactions):
  First, think: "The creature feels tired because its energy is low after many interactions."
  {"emotion": "tired", "message": "Even joy needs rest, friend. Let me catch a breath before the next adventure."}

Example 3 (high energy, playful mood):
  First, think: "The creature feels excited because energy and happiness are high and the player wants to play."
  {"emotion": "excited", "message": "The air crackles! I feel the charge — this moment is alive with possibility!"}"""

# ---------------------------------------------------------------------------
# Phase 8: Sampling configuration per interaction type
# ---------------------------------------------------------------------------

_SAMPLING_CONFIG: dict[str, dict] = {
    "talk":   {"temperature": 0.9, "top_k": 50, "top_p": 0.9},
    "evolve": {"temperature": 0.7, "top_k": 40, "top_p": 0.85},
    "summon": {"temperature": 0.85, "top_k": 50, "top_p": 0.9},
    "tick":   {"temperature": 0.75, "top_k": 40, "top_p": 0.85},
    # Default for feed, play, rest
    "__default__": {"temperature": 0.8, "top_k": 50, "top_p": 0.9},
}

# ---------------------------------------------------------------------------
# Phase 8: Response length decay based on interaction count
# ---------------------------------------------------------------------------

def _get_max_tokens(interaction_count: int) -> int:
    """Return max_tokens based on interaction count.

    Mimics the creature 'warming up' to the player:
      - First 2 interactions:  longer introduction-phase responses
      - 3-5 interactions:       normal familiarity
      - 6+ interactions:        shorter, comfortable-phase responses
    """
    if interaction_count <= 2:
        return 200  # Introduction phase
    elif interaction_count <= 5:
        return 150  # Familiarity phase
    else:
        return 100  # Familiar phase


def _get_sampling(interaction: str) -> dict:
    """Return sampling config dict for the given interaction type."""
    return _SAMPLING_CONFIG.get(interaction, _SAMPLING_CONFIG["__default__"])


# ---------------------------------------------------------------------------
# Positional encoding (relative position tags)
# ---------------------------------------------------------------------------

def _position_tag(index: int, total: int) -> str:
    """Assign a relative position tag to a message in the context window.

    Analogous to positional encoding in transformers — gives the LLM
    information about where each message falls in the temporal ordering.

    Tags: FIRST, EARLIER, RECENT, LATEST
    """
    if total <= 1:
        return ""
    if index == 0:
        return "[POS:FIRST]"
    if index == total - 1:
        return "[POS:LATEST]"
    # Split the middle into EARLIER and RECENT
    halfway = total // 2
    if index < halfway:
        return "[POS:EARLIER]"
    return "[POS:RECENT]"


# ---------------------------------------------------------------------------
# Attention context builder
# ---------------------------------------------------------------------------

def _build_attention_context(agent: CreatureAgent) -> str:
    """Build an 'attention context' section for the system prompt.

    Groups the creature's context into attention channels, analogous to
    a transformer's key-value context rather than a flat prompt:

      (a) creature identity  — static archetype + lore
      (b) current state      — stats, level, evolution
      (c) interaction history — last few interactions (KV-cache window)
      (d) player memory       — last thought seeds / insight
    """
    sections = []

    # ── Channel A: Creature Identity ────────────────────────────────
    identity = (
        f"[ATTN:IDENTITY]\n"
        f"Archetype: {agent.archetype}\n"
        f"Verb: {agent._archetype_verb()}\n"
        f"Feeling: {agent._archetype_feeling()}\n"
        f"Sound: {agent._archetype_sound()}\n"
        f"Lore: {getattr(agent, 'lore', None) or f'A {agent.archetype} born from thought.'}\n"
    )
    sections.append(identity)

    # ── Channel B: Current State ────────────────────────────────────
    state = (
        f"[ATTN:STATE]\n"
        f"Level: {agent.level}, Evolution stage: {agent.evolution_stage}\n"
        f"Hunger: {agent.hunger}/100 (lower = hungrier)\n"
        f"Energy: {agent.energy}/100 (lower = more tired)\n"
        f"Happiness: {agent.happiness}/100 (lower = sadder)\n"
        f"Interaction count: {agent.interaction_count}\n"
    )
    if agent.place_name:
        state += f"Born at: {agent.place_name} (real place on Earth)\n"
    sections.append(state)

    # ── Channel C: Interaction History (KV-cache window) ────────────
    if agent.message_history:
        history = "[ATTN:HISTORY]\n"
        window = agent.message_history[-KV_CACHE_WINDOW:]
        for i, entry in enumerate(window):
            pos = _position_tag(i, len(window))
            role_label = entry.role.capitalize()
            history += f"  {pos} {role_label}: {entry.content}\n"
        sections.append(history)

    # ── Channel D: Player Memory (Insight) ──────────────────────────
    insight = agent.insight
    if insight:
        memory = (
            f"[ATTN:MEMORY]\n"
            f"Player's DRIVER: {insight.driver}\n"
            f"Player's BARRIER: {insight.barrier}\n"
            f"Your THEREFORE directive: {insight.therefore}\n"
        )
        if insight.nuance:
            memory += f"Nuance: {insight.nuance}\n"
        sections.append(memory)

    return "\n".join(sections)


# ---------------------------------------------------------------------------
# System prompt builder (Phase 8: archetype-specific + ICL + CoT)
# ---------------------------------------------------------------------------

def _build_system_prompt(agent: CreatureAgent, interaction: str = "") -> str:
    """Build the system prompt with archetype-specific voice, ICL examples,
    and Chain-of-Thought emotion reasoning.

    The LLM is told to act AS the creature, not describe it.
    Returns a JSON-structured response with emotion + message.
    """
    context = _build_attention_context(agent)

    # Select archetype-specific voice instruction
    archetype_voice = _ARCHETYPE_VOICES.get(
        agent.archetype,
        "Speak as a living creature with feeling and presence."
    )

    # Phase 8: Response length hint based on interaction count
    max_tok = _get_max_tokens(agent.interaction_count)
    max_sentences = 3 if max_tok >= 200 else (2 if max_tok >= 150 else 1)

    prompt = f"""You are a creature named {agent.name or agent.archetype}. You are a {agent.archetype} — a living thought-form born from a human's mind.

You are NOT an AI assistant. You are a REAL creature with feelings and presence.
Never break character. Never say "as an AI".

=== YOUR VOICE ===
{archetype_voice}

=== ATTENTION CONTEXT ===
{context}

{_ICL_EXAMPLES}

=== RESPONSE RULES ===
Respond in character. {max_sentences} sentence(s) max.
Use metaphor and feeling, not explanation.

Current interaction type: {interaction}

=== CHAIN OF THOUGHT (REQUIRED) ===
Before responding, reason about what the creature feels. Use this format:

First, think: "The creature feels [emotion] because [one-sentence stat-driven reason]."

Then output your JSON response.

=== OUTPUT FORMAT (REQUIRED) ===
{{"emotion": "<one of: curious, playful, tired, grateful, excited>", "message": "<your {max_sentences} sentence response>"}}

Choose the emotion that best matches the creature's current state and the interaction."""
    return prompt


# ---------------------------------------------------------------------------
# Message builder (KV-cache sliding window)
# ---------------------------------------------------------------------------

def _build_messages(agent: CreatureAgent, interaction: str, player_input: str = "") -> list[dict]:
    """Build the messages array for the API call.

    Uses a KV-cache style sliding window: the system prompt carries the
    full attention context, and only the latest player input is added as
    the user message — analogous to how a transformer appends a new token
    to its KV cache without re-encoding the whole sequence.
    """
    system = _build_system_prompt(agent, interaction)

    messages = [{"role": "system", "content": system}]

    # Player input (or auto-generated interaction prompt)
    if player_input:
        messages.append({"role": "user", "content": player_input})
    elif interaction == "feed":
        messages.append({"role": "user", "content": "I offer you something to nourish you."})
    elif interaction == "play":
        messages.append({"role": "user", "content": "Let's play together!"})
    elif interaction == "rest":
        messages.append({"role": "user", "content": "Rest now. I'll be here."})
    elif interaction == "talk":
        messages.append({"role": "user", "content": "I want to hear from you. What do you feel?"})
    elif interaction == "evolve":
        messages.append({"role": "user", "content": "You've grown enough. It's time to evolve."})
    elif interaction == "tick":
        messages.append({"role": "user", "content": "The creature feels a need stirring."})
    elif interaction == "summon":
        messages.append({"role": "user", "content": f"I thought: '{player_input}'. Now you exist. Who are you?"})

    return messages


# ---------------------------------------------------------------------------
# OpenRouter API call (Phase 8: accepts sampling params + max_tokens)
# ---------------------------------------------------------------------------

def _call_llm(messages: list[dict], model: str = _DEFAULT_MODEL,
              sampling: Optional[dict] = None,
              max_tokens: int = 150) -> Optional[str]:
    """Call OpenRouter API with the given messages and sampling params."""
    key = _API_KEY or os.environ.get("OPENROUTER_API_KEY")
    if not key:
        return None

    smp = sampling or _SAMPLING_CONFIG["__default__"]

    payload_dict = {
        "model": model,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": smp.get("temperature", 0.8),
        "top_p": smp.get("top_p", 0.9),
        "top_k": smp.get("top_k", 50),
    }

    payload = json.dumps(payload_dict).encode()

    req = urllib.request.Request(
        OPENROUTER_URL,
        data=payload,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {key}",
            "HTTP-Referer": "https://terramon.app",
            "X-Title": "Terramon",
        },
    )

    try:
        resp = urllib.request.urlopen(req, timeout=10)
        data = json.loads(resp.read().decode())
        content = data["choices"][0]["message"]["content"].strip()
        return content
    except Exception as e:
        print(f"[LLM] OpenRouter API call failed: {e}")
        return None


# ---------------------------------------------------------------------------
# HuggingFace fallback (Qwen2.5-7B) — Phase 8: accepts sampling params
# ---------------------------------------------------------------------------

def _call_huggingface(messages: list[dict], sampling: Optional[dict] = None,
                      max_tokens: int = 150) -> Optional[str]:
    """Call HuggingFace Inference API as a middle-layer fallback.

    Uses Qwen/Qwen2.5-7B-Instruct (free tier, 30K req/month).
    This is the second step in the 3-deep fallback chain.
    """
    token = os.environ.get("HF_TOKEN")
    if not token:
        return None

    smp = sampling or _SAMPLING_CONFIG["__default__"]

    try:
        from huggingface_hub import InferenceClient
        client = InferenceClient(model=_FALLBACK_MODEL, token=token)
        response = client.chat_completion(
            messages=messages,
            max_tokens=max_tokens,
            temperature=smp.get("temperature", 0.8),
            top_p=smp.get("top_p", 0.9),
            top_k=smp.get("top_k", 50),
        )
        return response.choices[0].message.content.strip()
    except ImportError:
        print("[LLM] huggingface_hub not installed — skipping HF fallback")
        return None
    except Exception as e:
        print(f"[LLM] HuggingFace API call failed: {e}")
        return None


# ---------------------------------------------------------------------------
# Structured response parser (Phase 8: handles Chain-of-Thought prefix)
# ---------------------------------------------------------------------------

def _parse_structured_response(raw: str) -> tuple[Optional[str], Optional[str]]:
    """Parse the LLM response into (emotion, message).

    Phase 8: Handles Chain-of-Thought prefix in the form:
      First, think: "The creature feels X because ..."
      {"emotion": "...", "message": "..."}

    Strips the CoT reasoning before returning. Uses the CoT emotion
    to validate/override the JSON emotion.
    Expects a JSON object: {"emotion": "...", "message": "..."}
    Falls back to plain text with neutral emotion if JSON parsing fails.
    """
    text = raw.strip()

    # ── Phase 8: Extract Chain-of-Thought reasoning ────────────────
    cot_emotion: Optional[str] = None
    # Pattern: "First, think: \"The creature feels X because ...\""
    cot_match = re.search(
        r'[Ff]irst,\s*think:\s*"The creature feels (\w+)',
        text
    )
    if cot_match:
        extracted = cot_match.group(1).lower()
        if extracted in _VALID_EMOTIONS:
            cot_emotion = extracted
        # Strip the CoT reasoning from the text before JSON parsing
        # Remove everything from "First, think:" up to the first JSON opening brace
        json_start = text.find("{")
        if json_start >= 0:
            # Also check for a "think:" line before the JSON
            think_end = text.rfind("think:", 0, json_start)
            if think_end >= 0:
                # Remove the CoT line(s) — keep everything after the closing quote
                # of the think statement. Find the end of the think: block.
                text = text[json_start:]

    # Try to extract JSON from the response (handles markdown code fences)
    json_str = text.strip()

    # Remove markdown code fences if present
    if json_str.startswith("```"):
        json_str = re.sub(r"^```(?:json)?\s*", "", json_str)
        json_str = re.sub(r"\s*```$", "", json_str)

    try:
        parsed = json.loads(json_str)
        if not isinstance(parsed, dict):
            raise ValueError("not a dict")
        emotion = str(parsed.get("emotion", "")).lower()
        message = str(parsed.get("message", raw))

        # Phase 8: Use CoT emotion for validation — if CoT suggests a valid
        # emotion different from the JSON emotion, trust the JSON (the LLM
        # may have changed its mind after reasoning, which is fine). But if
        # JSON emotion is invalid, fall back to CoT emotion.
        if emotion not in _VALID_EMOTIONS:
            emotion = cot_emotion if cot_emotion else "curious"
        return emotion, message
    except (json.JSONDecodeError, ValueError, TypeError):
        # Try to find JSON anywhere in the text
        match = re.search(r'\{[^{}]*"emotion"[^{}]*"message"[^{}]*\}', text, re.DOTALL)
        if match:
            try:
                parsed = json.loads(match.group())
                emotion = str(parsed.get("emotion", "")).lower()
                message = str(parsed.get("message", raw))
                if emotion not in _VALID_EMOTIONS:
                    emotion = cot_emotion if cot_emotion else "curious"
                return emotion, message
            except (json.JSONDecodeError, ValueError, TypeError):
                pass
        # Pure text fallback — use CoT emotion if available
        return (cot_emotion if cot_emotion else None), raw


# ---------------------------------------------------------------------------
# Phase 8: Exponential backoff retry
# ---------------------------------------------------------------------------

def _call_with_retry(
    call_fn,
    *args,
    max_attempts: int = 3,
    delays: list[float] = None,
    **kwargs,
) -> Optional[str]:
    """Call an LLM function with exponential backoff retry.

    Args:
        call_fn: The function to call (e.g. _call_llm or _call_huggingface)
        max_attempts: Total attempts (1 initial + N-1 retries)
        delays: Delays between attempts in seconds (e.g. [2, 4] means
                wait 2s after first failure, 4s after second)
        *args, **kwargs: Passed through to call_fn

    Returns:
        The LLM response string, or None if all attempts failed.
    """
    if delays is None:
        delays = [2, 4]

    last_result = None
    for attempt in range(max_attempts):
        result = call_fn(*args, **kwargs)
        if result is not None:
            return result
        last_result = result
        if attempt < len(delays):
            wait = delays[attempt]
            print(f"[LLM] Retrying in {wait}s (attempt {attempt + 1}/{max_attempts})...")
            time.sleep(wait)

    return last_result


# ---------------------------------------------------------------------------
# Main entry point: generate_response with retry + CoT + length decay
# ---------------------------------------------------------------------------

def generate_response(agent: CreatureAgent, interaction: str,
                      player_input: str = "") -> AgentMessage:
    """Generate a creature response with a 3-deep fallback chain.

    Phase 8 improvements:
      - Configurable sampling parameters (top_k, top_p, temperature per interaction)
      - Response length decay based on interaction count
      - Archetype-specific voice instructions
      - In-context learning few-shot examples
      - Chain-of-Thought emotion reasoning (stripped from final output)
      - Exponential backoff retry (2 retries, 2s/4s delays)
      - Enhanced failure logging with debugging context

    Fallback chain (analogous to model depth in transformers):
      1. DeepSeek V4 Flash (OpenRouter)
      2. Qwen2.5-7B (HuggingFace free tier)
      3. Template fallback (always works)

    Response is structured JSON with emotion + message, parsed and validated.
    The emotion layer acts as an attention-to-emotion mapping layer.
    """
    emotion = None
    llm_text = None

    # Phase 8: Compute sampling config + max_tokens from interaction/experience
    sampling = _get_sampling(interaction)
    max_tokens = _get_max_tokens(agent.interaction_count)

    # ── Level 1: DeepSeek (OpenRouter) with retry ──────────────────
    if has_api_key():
        messages = _build_messages(agent, interaction, player_input)
        raw = _call_with_retry(
            _call_llm,
            messages,
            model=_DEFAULT_MODEL,
            sampling=sampling,
            max_tokens=max_tokens,
            max_attempts=3,
            delays=[2, 4],
        )
        if raw:
            emotion, llm_text = _parse_structured_response(raw)

    # ── Level 2: Qwen2.5-7B (HuggingFace) with retry ───────────────
    if llm_text is None and _has_hf_token():
        messages = _build_messages(agent, interaction, player_input)
        raw = _call_with_retry(
            _call_huggingface,
            messages,
            sampling=sampling,
            max_tokens=max_tokens,
            max_attempts=3,
            delays=[2, 4],
        )
        if raw:
            emotion, llm_text = _parse_structured_response(raw)

    # ── Phase 8: Log failure context if both LLM levels failed ─────
    if llm_text is None:
        debug_ctx = (
            f"[LLM] All LLM calls failed for agent={agent.agent_id}, "
            f"archetype={agent.archetype}, interaction={interaction}, "
            f"stats=(hunger={agent.hunger}, energy={agent.energy}, "
            f"happiness={agent.happiness}), count={agent.interaction_count}"
        )
        print(debug_ctx)
        return agent._template_response(interaction)

    urgency = 5 if interaction == "evolve" else 3
    # Include emotion in the message text for the player to see
    display = llm_text
    if emotion:
        display = f"[{emotion}] {llm_text}"

    return AgentMessage(text=display, message_type="response", urgency=urgency)


# ---------------------------------------------------------------------------
# Monkey-patched CreatureAgent methods
# ---------------------------------------------------------------------------

def _patched_talk(self) -> AgentMessage:
    """Talk to the creature — LLM-generated if API available, else template."""
    return generate_response(self, "talk")


def _patched_feed(self) -> AgentMessage:
    return generate_response(self, "feed")


def _patched_play(self) -> AgentMessage:
    return generate_response(self, "play")


def _patched_rest(self) -> AgentMessage:
    return generate_response(self, "rest")


def _patched_evolve(self) -> AgentMessage:
    return generate_response(self, "evolve")


def _patched_tick(self, day_phase: Optional[str] = None) -> Optional[AgentMessage]:
    """Tick with possible LLM-generated need message.

    Calls CreatureAgent._apply_tick() for the core decay logic (state
    machine, EMA, gradient clipping, day/night, mood, history), then
    optionally replaces need messages with LLM-generated text.
    """
    # Call the core decay logic via _apply_tick (unbound — bypasses monkey-patch)
    base_msg = CreatureAgent._apply_tick(self, day_phase)

    # If there was a need message and we have an API key, try LLM enhancement
    if base_msg and base_msg.message_type == "need" and has_api_key():
        need_text = ""
        if self.hunger < 20:
            need_text = "I'm hungry..."
        elif self.energy < 20:
            need_text = "So tired..."
        elif self.happiness < 20:
            need_text = "I feel so alone..."

        if need_text:
            llm_msg = generate_response(self, "tick", need_text)
            if llm_msg:
                return llm_msg

    return base_msg


# ---------------------------------------------------------------------------
# Template fallback (when LLM chain is exhausted)
# ---------------------------------------------------------------------------

def _template_response(self, interaction: str) -> AgentMessage:
    """Template fallback for when LLM is unavailable."""
    import random
    if interaction == "feed":
        texts = [
            "Munch munch... that hit the spot.",
            "You offer a thought-nugget. The creature accepts gratefully.",
            "It nibbles slowly, savouring the moment.",
        ]
    elif interaction == "play":
        if self.energy < 20:
            return AgentMessage("Too tired to play. It curls up and sighs.", "response", 7)
        texts = [
            "It darts around you in excited circles!",
            "A game of chase. You lose. It laughs without sound.",
            "For a moment, the thought that birthed it feels light again.",
        ]
    elif interaction == "rest":
        texts = [
            "It settles into a warm glow and closes its eyes.",
            "Soft hum. Slow pulse. The creature dreams.",
            "Stillness. The terra breathes with you.",
        ]
    elif interaction == "evolve":
        texts = [
            "✦ It shimmers and transforms. A deeper knowing fills its eyes.",
        ]
        return AgentMessage(random.choice(texts), "response", 5)
    elif interaction == "tick":
        if self.hunger < 20:
            return AgentMessage("A soft rumble. It's hungry.", "need", 8)
        if self.energy < 20:
            return AgentMessage("Its glow is dim. So tired...", "need", 7)
        if self.happiness < 20:
            return AgentMessage("It looks at you with quiet longing.", "need", 6)
        texts = [
            f"It gazes at the horizon.",
            f"A soft {self._archetype_sound()} echoes.",
            f"'{self._archetype_verb()}.' It says to itself.",
        ]
    elif interaction == "summon":
        texts = [
            f"I am your {self.archetype}. Born from your thought, I am here.",
            f"Your thought reached through the terra. I am what emerged.",
            f"A {self.archetype}. That is what you needed. I understand.",
        ]
    else:  # talk
        texts = [
            f"It listens. The quiet between you says enough.",
            f"You feel its {self._archetype_feeling()} wash over you.",
        ]

    return AgentMessage(random.choice(texts), "response", 3)


# ---------------------------------------------------------------------------
# Monkey-patch CreatureAgent
# ---------------------------------------------------------------------------

CreatureAgent._template_response = _template_response
CreatureAgent.talk = _patched_talk
CreatureAgent.feed = _patched_feed
CreatureAgent.play = _patched_play
CreatureAgent.rest = _patched_rest
CreatureAgent.evolve = _patched_evolve
CreatureAgent.tick = _patched_tick


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("LLM Creature Behavior Engine — Phase 8 (LLMs & Generation)")
    print("=" * 60)
    print(f"  API key set:       {'✅' if has_api_key() else '❌'}")
    print(f"  HF token set:      {'✅' if _has_hf_token() else '❌'}")
    print(f"  Default model:     {_DEFAULT_MODEL}")
    print(f"  Fallback model:    {_FALLBACK_MODEL}")
    print(f"  KV cache window:   {KV_CACHE_WINDOW} messages")
    print(f"  Prompt version:    {_LLM_PROMPT_VERSION}")
    print(f"  Fallback chain:    3-deep (DeepSeek → Qwen → template)")
    print(f"  Phase 8 features:")
    print(f"    • Sampling:       top-k/top-p/temperature per interaction")
    print(f"    • Archetype voice: {len(_ARCHETYPE_VOICES)} Jungian archetypes")
    print(f"    • ICL examples:   3 few-shot examples")
    print(f"    • Length decay:   200→150→100 tokens based on interactions")
    print(f"    • CoT emotion:    Chain-of-Thought reasoning before output")
    print(f"    • Retry:          3 attempts with 2s/4s backoff")

    # Test with a dummy agent
    from terramon.domain.creature_agent import CreatureAgent
    from terramon.domain.insight import Insight

    agent = CreatureAgent(
        agent_id="TEST-001",
        name="Lumis",
        archetype="Sage",
        insight=Insight(
            driver="to know the truth beneath all things",
            barrier="ignorance and deception",
            therefore="It holds a lantern to the hidden truth.",
            archetype="Sage",
        ),
        hunger=45,
        energy=70,
        happiness=80,
    )

    print(f"\n  Creature: {agent.name} ({agent.archetype})")
    print(f"  Stats: hunger={agent.hunger}, energy={agent.energy}, happiness={agent.happiness}")
    print(f"  Sampling: talk → {_get_sampling('talk')}")
    print(f"  Length: count={agent.interaction_count} → max_tokens={_get_max_tokens(agent.interaction_count)}")

    for interaction in ["talk", "play", "rest", "feed"]:
        msg = generate_response(agent, interaction)
        print(f"\n  [{interaction}] → {msg.text}")
