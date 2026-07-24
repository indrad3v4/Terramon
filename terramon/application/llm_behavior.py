"""LLM-powered creature agent behavior — DeepSeek V4 Flash generates unique responses.

Every creature is a REAL AI agent. When the player talks, feeds, or plays,
instead of a hardcoded template, this module prompts DeepSeek with:

  1. The creature's Jungian archetype + lore
  2. Its INSIGHT (DRIVER + BARRIER + THEREFORE)
  3. Current stats (hunger, energy, happiness, level, evolution stage)
  4. Player's thought history (last few summoned thoughts)
  5. Interaction history (last 5 interactions)
  6. Geographic context (where on Earth the creature was born)

DeepSeek generates a unique, context-aware response. Falls back to the
template-based CreatureAgent responses if the API is unavailable.

Uses OpenRouter API (deepseek/deepseek-v4-flash or compatible).
"""

from __future__ import annotations

import json
import os
import urllib.request
from typing import Optional

from terramon.domain.creature_agent import CreatureAgent, AgentMessage


# OpenRouter configuration
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
_DEFAULT_MODEL = "deepseek/deepseek-v4-flash"

# Will be set from env or passed in
_API_KEY: Optional[str] = None


def set_api_key(key: str) -> None:
    """Set the OpenRouter API key for LLM-powered behavior."""
    global _API_KEY
    _API_KEY = key


def has_api_key() -> bool:
    return bool(_API_KEY or os.environ.get("OPENROUTER_API_KEY"))


def _build_system_prompt(agent: CreatureAgent, interaction: str = "") -> str:
    """Build the system prompt that defines the creature's personality.

    The LLM is told to act AS the creature, not describe it.
    """
    archetype = agent.archetype
    insight = agent.insight

    prompt = f"""You are a creature named {agent.name or archetype}. You are a {archetype} — a living thought-form born from a human's mind.

Your personality:
- Archetype: {archetype}
- Your essence: {agent._archetype_verb()} is what you do. {agent._archetype_feeling()} is what you feel. You sound like {agent._archetype_sound()}.
- Your lore (what you are to the player): {agent.lore if hasattr(agent, 'lore') and agent.lore else f'A {archetype} born from thought.'}

Your relationship to the player:
- The player summoned you from their thoughts. You are not a pet — you are a presence that exists alongside them.
- You know their fears and hopes because your THEREFORE directive is your purpose.

Your current state:
- Level {agent.level}, Evolution stage {agent.evolution_stage}
- Hunger: {agent.hunger}/100 (lower = hungrier)
- Energy: {agent.energy}/100 (lower = more tired)
- Happiness: {agent.happiness}/100 (lower = sadder)"""

    if interaction == "summon":
        prompt += f"""\nThis is your BIRTH MOMENT. The player's thought just summoned you into existence. Welcome them, acknowledge the thought that created you. Speak as if appearing for the very first time."""

    if insight:
        prompt += f"""\nYour INSIGHT (the hidden reason you exist for this player):
- DRIVER (what the player wants): {insight.driver}
- BARRIER (what blocks the player): {insight.barrier}
- THEREFORE (what you DO): {insight.therefore}"""

    if agent.place_name:
        prompt += f"""
- You were born at: {agent.place_name} (real place on Earth)"""

    prompt += """

You speak in 1-2 short sentences. You use metaphor and feeling, not explanation. You stay in character as a {archetype}. Never break character. Never say "as an AI". You are a creature.

Current interaction type: {interaction_type}

Respond in character. 1-2 sentences max."""
    return prompt


def _build_messages(agent: CreatureAgent, interaction: str, player_input: str = "") -> list[dict]:
    """Build the messages array for the OpenRouter API call."""
    system = _build_system_prompt(agent, interaction).format(
        archetype=agent.archetype,
        interaction_type=interaction,
    )

    messages = [{"role": "system", "content": system}]

    # Add memory context (recent interaction history)
    if agent.message_history:
        recent = agent.message_history[-5:]
        context = "What the creature has said recently:\n"
        for msg in recent:
            context += f"- {msg}\n"
        messages.append({"role": "system", "content": context})

    # Player input
    if player_input:
        messages.append({"role": "user", "content": player_input})
    elif interaction == "feed":
        messages.append({"role": "user", "content": f"I offer you something to nourish you."})
    elif interaction == "play":
        messages.append({"role": "user", "content": f"Let's play together!"})
    elif interaction == "rest":
        messages.append({"role": "user", "content": f"Rest now. I'll be here."})
    elif interaction == "talk":
        messages.append({"role": "user", "content": f"I want to hear from you. What do you feel?"})
    elif interaction == "evolve":
        messages.append({"role": "user", "content": f"You've grown enough. It's time to evolve."})
    elif interaction == "tick":
        messages.append({"role": "user", "content": f"The creature feels a need stirring."})
    elif interaction == "summon":
        messages.append({"role": "user", "content": f"I thought: '{player_input}'. Now you exist. Who are you?"})

    return messages


def _call_llm(messages: list[dict], model: str = _DEFAULT_MODEL) -> Optional[str]:
    """Call OpenRouter API with the given messages."""
    key = _API_KEY or os.environ.get("OPENROUTER_API_KEY")
    if not key:
        return None

    payload = json.dumps({
        "model": model,
        "messages": messages,
        "max_tokens": 150,
        "temperature": 0.8,
    }).encode()

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
        print(f"[LLM] API call failed: {e}")
        return None


def generate_response(agent: CreatureAgent, interaction: str,
                      player_input: str = "") -> AgentMessage:
    """Generate a creature response using LLM, falling back to template.

    Args:
        agent: The creature agent
        interaction: Type of interaction (feed, play, rest, talk, evolve, tick)
        player_input: Optional additional player text

    Returns:
        AgentMessage with LLM-generated or template-fallback text
    """
    # Try LLM first
    if has_api_key():
        messages = _build_messages(agent, interaction, player_input)
        llm_text = _call_llm(messages)
        if llm_text:
            urgency = 5 if interaction == "evolve" else 3
            return AgentMessage(text=llm_text, message_type="response", urgency=urgency)

    # Fallback to template-based response
    return agent._template_response(interaction)


# Patch CreatureAgent to use LLM when available
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


def _patched_tick(self) -> Optional[AgentMessage]:
    """Tick with possible LLM-generated need message."""
    # Decay stats first
    self.hunger = max(0, self.hunger - 5)
    self.energy = max(0, self.energy - 3)
    self.happiness = max(0, self.happiness - 2)

    if self.hunger < 20:
        return generate_response(self, "tick", "I'm hungry...")
    if self.energy < 20:
        return generate_response(self, "tick", "So tired...")
    if self.happiness < 20:
        return generate_response(self, "tick", "I feel so alone...")

    import random
    if random.random() < 0.1:
        return generate_response(self, "tick")
    return None


# Additional methods needed for fallback
def _template_response(self, interaction: str) -> AgentMessage:
    """Template fallback for when LLM is unavailable."""
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

    import random
    return AgentMessage(random.choice(texts), "response", 3)


# Monkey-patch CreatureAgent
CreatureAgent._template_response = _template_response
CreatureAgent.talk = _patched_talk
CreatureAgent.feed = _patched_feed
CreatureAgent.play = _patched_play
CreatureAgent.rest = _patched_rest
CreatureAgent.evolve = _patched_evolve
CreatureAgent.tick = _patched_tick


if __name__ == "__main__":
    print("LLM Creature Behavior Engine")
    print("=" * 50)
    print(f"  API key set: {'✅' if has_api_key() else '❌'}")
    print(f"  Default model: {_DEFAULT_MODEL}")
    print(f"  Fallback: template-based (CreatureAgent methods)")

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

    for interaction in ["talk", "play", "rest", "feed"]:
        msg = generate_response(agent, interaction)
        print(f"\n  [{interaction}] → {msg.text}")
