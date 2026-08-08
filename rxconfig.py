"""Reflex config for Terramon TMA (Telegram Mini App / Web PWA).

Deploys as a static+backend Reflex app (Railway-ready). The frontend is a React
SPA compiled from Python; the backend runs the summon domain logic in Python.
"""

import reflex as rx
from reflex_base.plugins.sitemap import SitemapPlugin

config = rx.Config(
    app_name="terramon_tma",
    telemetry_enabled=False,
    disable_plugins=[SitemapPlugin],
    # TMA fix: Telegram WebView blocks/breaks WebSocket to third-party hosts,
    # so on_click events never reach the backend (tutorial "Got it!" dead,
    # SUMMON dead — every button). HTTP polling works in any WebView.
    transport="polling",
)
