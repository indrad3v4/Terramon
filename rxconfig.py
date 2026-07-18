"""Reflex config for Terramon TMA (Telegram Mini App / Web PWA).

Deploys as a static+backend Reflex app (Railway-ready). The frontend is a React
SPA compiled from Python; the backend runs the summon domain logic in Python.
"""

import reflex as rx

config = rx.Config(
    app_name="terramon_tma",
    # Railway/prod: set API URL via env; local defaults are fine.
    telemetry_enabled=False,
)
