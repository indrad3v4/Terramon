"""Reflection generation for creature memory (Generative Agents, ch. 3).

A reflection is ONE high-level insight sentence synthesized from recent
observations, e.g. 'Я понял(а), что боюсь не одиночества, а того, что
меня забудут'. The LLM is injected as llm_call(prompt, system) -> str so
this module stays offline-testable; on failure/None the deterministic
fallback picks the highest-importance observation and templates it.
"""

from __future__ import annotations

from terramon.agents.memory_stream import MemoryEntry, MemoryStream

REFLECTION_CONTEXT = 10  # how many recent observations to consider

_FALLBACK_TEMPLATE = "Мне важно помнить: {text}"

_SYSTEM = (
    "Ты — внутренний голос существа из игры Terramon. Ты говоришь на русском. "
    "Ты замечаешь закономерности в своих наблюдениях и формулируешь их одним "
    "предложением — глубоким, личным, без общих слов и без пояснений."
)


def _build_prompt(recent: list[MemoryEntry]) -> str:
    lines = "\n".join(f"{i}. {entry.text}" for i, entry in enumerate(recent, 1))
    return (
        "Вот мои последние наблюдения:\n"
        f"{lines}\n\n"
        "Какая ОДНА важная мысль об этом? Ответь одним предложением на русском, "
        "от первого лица, без кавычек и пояснений."
    )


def _clean(text: str) -> str:
    """Strip quotes/whitespace an LLM might wrap the insight in."""
    return text.strip().strip('"').strip("«»").strip()


def generate_reflection(stream: MemoryStream, llm_call) -> str:
    """Return one high-level insight sentence from recent observations.

    Uses the injected llm_call(prompt, system) when available; if it is
    missing, returns None, raises, or produces an unusable answer, falls
    back to the highest-importance observation templated as
    'Мне важно помнить: {text}'.
    """
    recent = stream.observations[-REFLECTION_CONTEXT:]
    if not recent:
        return "Мне пока не о чем задуматься."

    if callable(llm_call):
        try:
            raw = llm_call(_build_prompt(recent), _SYSTEM)
            text = _clean(raw) if isinstance(raw, str) else ""
            if len(text) >= 8 and any(ch.isalpha() for ch in text):
                return text
        except Exception:
            pass  # deterministic fallback below

    top = max(recent, key=lambda entry: entry.importance)
    return _FALLBACK_TEMPLATE.format(text=top.text)
