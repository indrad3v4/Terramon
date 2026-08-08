"""Daily planning + lazy offline ticks for Terramon creatures.

Generative Agents planning layer, budget-adapted:

  - make_daily_plan: 3-5 activities per day derived from the creature's
    archetype + recent reflections. The LLM only writes the one-line day
    summary (optional); the deterministic fallback always works.
  - simulate_offline: the LAZY TICK — when a player returns after `days`
    away, render a short Russian diary of what the creature did while
    they were gone. Deterministic per-archetype templates + hour-of-day;
    at most max_llm_calls LLM calls (default 1) for the period reflection.

Pure stdlib; llm_call is always injected, never imported.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import date, datetime

from terramon.agents.memory_stream import MemoryStream

# ---------------------------------------------------------------------------
# Archetype -> daily activities (4 each, rotated by day-of-year for variety).
# Keys: Jung's 12 archetypes from the repo's embedding classifier plus the
# emotional keys used in-game (mapped to archetypes below).
# ---------------------------------------------------------------------------

_ACTIVITIES: dict[str, list[str]] = {
    "innocent": [
        "искать безопасное место",
        "прятаться от грозы в шкафу",
        "пересчитывать свои вещи",
        "смотреть на спящих и улыбаться",
    ],
    "orphan": [
        "сидеть у окна и ждать",
        "искать следы тех, кто ушёл",
        "прижиматься к тёплым стенам",
        "собирать потерянные вещи",
    ],
    "hero": [
        "тренироваться до темноты",
        "проверять, что стены крепкие",
        "защищать слабых у реки",
        "покорять самый высокий холм",
    ],
    "caregiver": [
        "кормить птиц у крыльца",
        "поправлять гнёзда",
        "греть лапами замёрзший ручей",
        "собирать ягоды для других",
    ],
    "explorer": [
        "гулять по незнакомым улицам",
        "забираться на крышу и смотреть вдаль",
        "идти за новым запахом",
        "отмечать на карте нехоженые места",
    ],
    "rebel": [
        "гулять у воды",
        "петь громко ночью",
        "переставлять камни на тропе",
        "рисовать мелом на асфальте",
    ],
    "lover": [
        "смотреть на звёзды",
        "сидеть у окна и ждать",
        "писать письмо, которое не отправишь",
        "слушать, как дышит город",
    ],
    "creator": [
        "лепить из глины фигурки",
        "придумывать новую песню",
        "собирать мозаику из листьев",
        "раскрашивать серые стены",
    ],
    "jester": [
        "придумывать игры с тенью",
        "смеяться с ветром",
        "прятаться и выскакивать",
        "считать ворон и загадывать желания",
    ],
    "sage": [
        "перебирать старые письма",
        "читать облака как книги",
        "записывать свои сны",
        "смотреть на луну и думать",
    ],
    "magician": [
        "шептать заклинания дождю",
        "превращать камни в сокровища",
        "зажигать светлячков",
        "менять воду в лужах местами",
    ],
    "ruler": [
        "обходить свои владения",
        "наводить порядок на поляне",
        "считать подданных-жуков",
        "строить трон из корней",
    ],
}

_DEFAULT_ACTIVITIES = [
    "сидеть у окна и ждать",
    "гулять по знакомым местам",
    "смотреть на звёзды",
    "думать о том, кто ушёл",
]

# Emotional keys used in-game -> Jungian archetype pools.
_EMOTION_TO_ARCHETYPE = {
    "fear": "innocent",
    "fear of the unknown": "innocent",
    "anger": "rebel",
    "loneliness": "lover",
    "shame": "sage",
    "longing": "lover",
}


def _normalize_archetype(archetype: str) -> str:
    key = (archetype or "").strip().lower().replace("_", " ").replace("-", " ")
    return _EMOTION_TO_ARCHETYPE.get(key, key)


def _activities_for(archetype: str) -> list[str]:
    key = _normalize_archetype(archetype)
    return list(_ACTIVITIES.get(key, _DEFAULT_ACTIVITIES))


# ---------------------------------------------------------------------------
# DailyPlan
# ---------------------------------------------------------------------------

@dataclass
class DailyPlan:
    """A creature's plan for one day."""

    date: str
    activities: list[str] = field(default_factory=list)
    summary: str = ""


_PLAN_SYSTEM = (
    "Ты — существо из игры Terramon. Составляешь план на день. Отвечай ОДНИМ "
    "предложением-резюме на русском, от первого лица, без пояснений."
)


def _fallback_summary(day: str, activities: list[str]) -> str:
    joined = "; ".join(activities[:3])
    return f"День {day}: {joined}."


def _shorten(text: str, limit: int = 120) -> str:
    text = text.strip()
    return text if len(text) <= limit else text[:limit - 1].rstrip() + "…"


def make_daily_plan(stream: MemoryStream, archetype: str, llm_call) -> DailyPlan:
    """Build a DailyPlan: 3-5 activities from archetype + recent reflections.

    Activities are deterministic (archetype pool rotated by day-of-year, plus
    one reflection-derived item when a reflection exists). The one-line
    summary uses the injected llm_call when it works, else a template.
    """
    today = date.today()
    pool = _activities_for(archetype)
    start = today.timetuple().tm_yday % len(pool)
    activities = pool[start:] + pool[:start]

    for ref in stream.reflections[-1:]:
        recalled = _shorten(ref.text)
        if recalled:
            activities = activities[:4] + [f"вспомнить: {recalled}"]

    while len(activities) < 3:  # safety: never fewer than 3 activities
        activities.append(pool[len(activities) % len(pool)])

    summary = _fallback_summary(today.isoformat(), activities)
    if callable(llm_call):
        try:
            prompt = (
                f"Я — существо-{archetype}. Сегодня {today.isoformat()}.\n"
                f"Мои недавние наблюдения: "
                f"{'; '.join(e.text for e in stream.observations[-5:])}\n"
                f"Мои недавние размышления: "
                f"{'; '.join(e.text for e in stream.reflections[-2:])}\n"
                "Напиши ОДНО предложение-резюме моего дня на русском, "
                "от первого лица."
            )
            raw = llm_call(prompt, _PLAN_SYSTEM)
            if isinstance(raw, str) and raw.strip():
                summary = raw.strip()
        except Exception:
            pass  # keep the deterministic summary

    return DailyPlan(date=today.isoformat(), activities=activities, summary=summary)


# ---------------------------------------------------------------------------
# Lazy offline tick: the 'пока тебя не было' diary
# ---------------------------------------------------------------------------

_DIARY: dict[str, list[str]] = {
    "innocent": [
        "Пока тебя не было, я {period} прятался(ась) в самом тёплом углу и слушал(а), как тихо.",
        "Пока тебя не было, я {period} пересчитывал(а) свои вещи, чтобы ничего не потерять.",
        "Пока тебя не было, я {period} сидел(а) в шкафу и ждал(а), пока гроза уйдёт.",
        "Пока тебя не было, я {period} смотрел(а) на дверь и верил(а), что она откроется.",
    ],
    "orphan": [
        "Пока тебя не было, я {period} сидел(а) у окна и ждал(а), когда ты вернёшься.",
        "Пока тебя не было, я {period} искал(а) следы тех, кто когда-то ушёл.",
        "Пока тебя не было, я {period} прижимался(ась) к тёплой стене и слушал(а), как дом дышит.",
        "Пока тебя не было, я {period} собирал(а) потерянные вещи, будто они чьи-то воспоминания.",
    ],
    "hero": [
        "Пока тебя не было, я {period} тренировался(ась) до темноты, чтобы стать сильнее.",
        "Пока тебя не было, я {period} проверял(а), что стены вокруг крепкие.",
        "Пока тебя не было, я {period} защищал(а) слабых у реки.",
        "Пока тебя не было, я {period} покорял(а) самый высокий холм и кричал(а) оттуда твоё имя.",
    ],
    "caregiver": [
        "Пока тебя не было, я {period} кормил(а) птиц у крыльца.",
        "Пока тебя не было, я {period} поправлял(а) гнёзда и грел(а) лапами замёрзший ручей.",
        "Пока тебя не было, я {period} собирал(а) ягоды для всех, кто голоден.",
        "Пока тебя не было, я {period} укрывал(а) листьями тех, кто спит на земле.",
    ],
    "explorer": [
        "Пока тебя не было, я {period} гулял(а) по незнакомым улицам и запоминал(а) их для тебя.",
        "Пока тебя не было, я {period} забирался(ась) на крышу и смотрел(а), не идёшь ли ты.",
        "Пока тебя не было, я {period} шёл(ла) за новым запахом и дошёл(ла) до реки.",
        "Пока тебя не было, я {period} отмечал(а) на карте нехоженые места.",
    ],
    "rebel": [
        "Пока тебя не было, я {period} гулял(а) у воды и кричал(а) на волны.",
        "Пока тебя не было, я {period} пел(а) громко, чтобы город не уснул.",
        "Пока тебя не было, я {period} переставлял(а) камни на тропе — пусть мир немного сдвинется.",
        "Пока тебя не было, я {period} рисовал(а) мелом на асфальте твой силуэт.",
    ],
    "lover": [
        "Пока тебя не было, я {period} смотрел(а) на звёзды и искал(а) среди них твою.",
        "Пока тебя не было, я {period} сидел(а) у окна и ждал(а) твоих шагов.",
        "Пока тебя не было, я {period} писал(а) письмо, которое никогда не отправлю.",
        "Пока тебя не было, я {period} слушал(а), как дышит город, и искал(а) в нём твоё дыхание.",
    ],
    "creator": [
        "Пока тебя не было, я {period} лепил(а) из глины маленьких нас.",
        "Пока тебя не было, я {period} придумывал(а) песню про то, как ты возвращаешься.",
        "Пока тебя не было, я {period} собирал(а) мозаику из листьев — получился портрет.",
        "Пока тебя не было, я {period} раскрашивал(а) серую стену в цвет твоих глаз.",
    ],
    "jester": [
        "Пока тебя не было, я {period} придумывал(а) игры с тенью, чтобы не скучать.",
        "Пока тебя не было, я {period} смеялся(ась) с ветром, хотя было не очень смешно.",
        "Пока тебя не было, я {period} прятался(ась) и выскакивал(а) — вдруг это ты?",
        "Пока тебя не было, я {period} считал(а) ворон и загадывал(а) на тебя.",
    ],
    "sage": [
        "Пока тебя не было, я {period} перебирал(а) старые письма и находил(а) в них ответы.",
        "Пока тебя не было, я {period} читал(а) облака как книги.",
        "Пока тебя не было, я {period} записывал(а) свои сны — в них ты приходил(а).",
        "Пока тебя не было, я {period} смотрел(а) на луну и понимал(а) что-то важное.",
    ],
    "magician": [
        "Пока тебя не было, я {period} шептал(а) заклинания дождю, чтобы он смыл расстояние.",
        "Пока тебя не было, я {period} превращал(а) камни в сокровища для тебя.",
        "Пока тебя не было, я {period} зажигал(а) светлячков и водил(а) их хороводом.",
        "Пока тебя не было, я {period} менял(а) воду в лужах местами, пока не вышло твоё отражение.",
    ],
    "ruler": [
        "Пока тебя не было, я {period} обходил(а) свои владения и следил(а) за порядком.",
        "Пока тебя не было, я {period} наводил(а) порядок на поляне — дом должен ждать тебя красивым.",
        "Пока тебя не было, я {period} считал(а) подданных-жуков и рассказывал(а) им о тебе.",
        "Пока тебя не было, я {period} строил(а) трон из корней — тебе на нём сидеть.",
    ],
}

_DEFAULT_DIARY = [
    "Пока тебя не было, я {period} сидел(а) у окна и ждал(а).",
    "Пока тебя не было, я {period} гулял(а) по знакомым местам и вспоминал(а) тебя.",
    "Пока тебя не было, я {period} смотрел(а) на звёзды и думал(а) о тебе.",
    "Пока тебя не было, я {period} разговаривал(а) с тишиной, и она отвечала.",
]


def _period_for_hour(hour: int) -> str:
    if 5 <= hour < 12:
        return "утром"
    if 12 <= hour < 18:
        return "днём"
    if 18 <= hour < 23:
        return "вечером"
    return "ночью"


def _diary_pool(archetype: str) -> list[str]:
    key = _normalize_archetype(archetype)
    return list(_DIARY.get(key, _DEFAULT_DIARY))


def simulate_offline(stream: MemoryStream,
                     days: float,
                     archetype: str,
                     llm_call=None,
                     max_llm_calls: int = 1) -> list[str]:
    """LAZY TICK: diary lines for `days` away from the player.

    Returns human-readable Russian lines ready for the UI: one optional
    LLM period-reflection (at most max_llm_calls calls, only when a
    stream and llm_call are available) plus ceil(days) deterministic
    per-archetype lines, each stamped with a time of day.
    """
    n_days = max(0.0, float(days))
    n_lines = max(1, math.ceil(n_days))
    pool = _diary_pool(archetype)
    now = datetime.now()
    hour = now.hour

    lines: list[str] = []
    if callable(llm_call) and max_llm_calls > 0 and stream.observations:
        try:
            prompt = (
                f"Я — существо-{archetype}. Меня не было видно {n_days:.1f} дн..\n"
                f"Мои наблюдения: "
                f"{'; '.join(e.text for e in stream.observations[-5:])}\n"
                "Что я делал(а), пока хозяин отсутствовал? Одно предложение "
                "на русском, от первого лица, начинающееся с «Пока тебя не было»."
            )
            raw = llm_call(prompt, _PLAN_SYSTEM)
            if isinstance(raw, str) and raw.strip():
                lines.append(raw.strip())
        except Exception:
            pass  # deterministic diary below

    start = (now.timetuple().tm_yday + hour) % len(pool)
    for i in range(n_lines):
        template = pool[(start + i) % len(pool)]
        period = _period_for_hour((hour + i * 6) % 24)
        lines.append(template.format(period=period))
    return lines
