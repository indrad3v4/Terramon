"""Resilient ``window.Telegram.WebApp`` mock for the Terramon KPI Playwright loop.

WHY
---
Headless Chromium has NO Telegram runtime: ``window.Telegram`` is undefined,
so every TMA-only path in the app is dead code during KPI runs:

- ``Telegram.WebApp.initData`` / ``initDataUnsafe.user`` (player identity —
  the report's M-blocker #2 wants per-player memory keyed by user id),
- ``Telegram.WebApp.LocationButton`` + ``onEvent('location_accessed')``
  (M1 geo bridge — ``_LOCATION_JS`` prefers it over navigator.geolocation),
- ``Telegram.WebApp.HapticFeedback.impactOccurred`` (summon/evolve haptics),
- ``Telegram.WebApp.openInvoice`` (M7 Stars rail),
- ``Telegram.WebApp.MainButton`` / ``showPopup`` / ``ready`` / ``expand`` ...

This module injects a SELF-HEALING mock of ``window.Telegram.WebApp`` BEFORE
the app loads via ``page.add_init_script`` so the app runs as a real TMA on
platform ``android``.

HONESTY CONTRACT
----------------
1. This is a MOCK, not the Telegram SDK. ``initData`` is well-formed but its
   ``hash`` is FAKE (SHA-256 of the data string) unless a real bot token is
   supplied — then the real HMAC-SHA256 signature is computed exactly like
   Telegram's backend does.
2. Every TMA method call is recorded in ``window.__TMA_MOCK__`` so the KPI
   report can state precisely which TMA-only features were exercised.
3. TMA-Studio (https://tma-studio.pages.dev) was investigated (source +
   live probe, 2026-08-09): the pages.dev site is a MARKETING LANDING PAGE
   (repo ``website/`` — Home/Features/FAQ), NOT an emulator, and it ignores
   query params such as ``?appUrl=``. The real emulator is a desktop Electron
   app that needs manual GUI setup (bot token + app URL + platform picker).
   So the default path is the injected mock; ``--tma-studio`` attempts the
   demo first and falls back to the mock honestly (see ``probe_tma_studio``).
"""

from __future__ import annotations

import hashlib
import hmac
import json
import time
import urllib.parse

DEFAULT_USER_ID = 710000000
DEFAULT_FIRST_NAME = "KPI Tester"
DEFAULT_USERNAME = "kpi_tester"
DEFAULT_PLATFORM = "android"
DEFAULT_VERSION = "8.0"
DEFAULT_COLOR_SCHEME = "dark"
MOCK_VERSION = "1.0.0"

TMA_STUDIO_DEFAULT_URL = "https://tma-studio.pages.dev"

# The JS mock. The literal ``__TMA_MOCK_CONFIG_JSON__`` is replaced at build
# time with the JSON-encoded config (JSON is a strict subset of JS object
# literals, so no escaping headaches).
_TMA_MOCK_JS = r"""
(function () {
  'use strict';
  var cfg = __TMA_MOCK_CONFIG_JSON__;
  var MOCK_VERSION = cfg.mockVersion || '1.0.0';

  var log = {
    injectedAt: Date.now(),
    platform: cfg.platform,
    version: cfg.version,
    colorScheme: cfg.colorScheme,
    initDataSigned: cfg.initDataSigned,
    user: cfg.initDataUnsafe.user,
    openInvoiceCalls: [],
    hapticCalls: [],
    mainButtonCalls: [],
    locationRequests: [],
    popupCalls: [],
    readyCalls: 0,
    expandCalls: 0,
    closeCalls: 0,
    events: {},
    emitted: []
  };

  var _listeners = {};
  var _isExpanded = true;

  function emit(event, data) {
    log.emitted.push({ event: String(event), ts: Date.now() });
    var cbs = (_listeners[event] || []).slice();
    for (var i = 0; i < cbs.length; i++) {
      try { cbs[i](data); } catch (e) { /* listener errors must not break the app */ }
    }
  }

  function onEvent(event, cb) {
    if (!_listeners[event]) _listeners[event] = [];
    _listeners[event].push(cb);
    log.events[event] = (log.events[event] || 0) + 1;
  }

  function offEvent(event, cb) {
    var arr = _listeners[event] || [];
    for (var i = arr.length - 1; i >= 0; i--) {
      if (!cb || arr[i] === cb) arr.splice(i, 1);
    }
  }

  function _ver(v) {
    return String(v).split('.').map(function (n) { return parseInt(n, 10) || 0; });
  }
  function _gte(a, b) {
    a = _ver(a); b = _ver(b);
    for (var i = 0; i < 3; i++) {
      if ((a[i] || 0) !== (b[i] || 0)) return (a[i] || 0) > (b[i] || 0);
    }
    return true;
  }

  function scheduleLocation(ll) {
    setTimeout(function () {
      emit('location_accessed', {
        latitude: ll[0], longitude: ll[1],
        altitude: null, course: null, speed: null
      });
    }, 300);
  }

  function makeButtonManager(name) {
    var state = { text: '', isVisible: false, isActive: true };
    function rec(method) {
      return function () {
        var arg = arguments.length ? String(arguments[0]) : undefined;
        log.mainButtonCalls.push({ name: name + '.' + method, arg: arg, ts: Date.now() });
      };
    }
    return {
      show: rec('show'),
      hide: rec('hide'),
      setText: function (t) { state.text = String(t); log.mainButtonCalls.push({ name: name + '.setText', arg: String(t), ts: Date.now() }); },
      setParams: rec('setParams'),
      setColors: rec('setColors'),
      enable: rec('enable'),
      disable: rec('disable'),
      onClick: rec('onClick'),
      offClick: rec('offClick'),
      text: state.text,
      isVisible: state.isVisible,
      isActive: state.isActive
    };
  }

  function makeWebApp() {
    var webApp = {
      __tmaMock: true,
      __tmaMockVersion: MOCK_VERSION,

      initData: cfg.initData,
      initDataUnsafe: cfg.initDataUnsafe,
      version: cfg.version,
      platform: cfg.platform,
      colorScheme: cfg.colorScheme,
      themeParams: cfg.themeParams,

      isExpanded: true,
      viewportHeight: 896,
      viewportStableHeight: 896,
      headerColor: '#1c1c1e',
      backgroundColor: '#1c1c1e',
      bottomBarColor: '#1c1c1e',
      isClosingConfirmationEnabled: false,
      isVerticalSwipesEnabled: true,

      isVersionAtLeast: function (v) { return _gte(cfg.version, v); },

      ready: function () { log.readyCalls += 1; },
      expand: function () { _isExpanded = true; log.expandCalls += 1; },
      close: function () { log.closeCalls += 1; },

      onEvent: onEvent,
      offEvent: offEvent,

      openInvoice: function (url, callback) {
        log.openInvoiceCalls.push({
          url: String(url),
          hasCallback: typeof callback === 'function',
          ts: Date.now()
        });
        if (typeof callback === 'function' && cfg.invoiceStatus !== null && cfg.invoiceStatus !== undefined) {
          setTimeout(function () {
            try { callback(cfg.invoiceStatus); } catch (e) { /* ignore */ }
          }, 0);
        }
      },

      showPopup: function (params, callback) {
        log.popupCalls.push({ name: 'showPopup', ts: Date.now() });
        if (typeof callback === 'function') {
          setTimeout(function () { try { callback('ok'); } catch (e) { /* ignore */ } }, 0);
        }
      },
      closePopup: function () { log.popupCalls.push({ name: 'closePopup', ts: Date.now() }); },
      showAlert: function (msg, callback) {
        log.popupCalls.push({ name: 'showAlert', ts: Date.now() });
        if (typeof callback === 'function') {
          setTimeout(function () { try { callback(); } catch (e) { /* ignore */ } }, 0);
        }
      },
      showConfirm: function (msg, callback) {
        log.popupCalls.push({ name: 'showConfirm', ts: Date.now() });
        if (typeof callback === 'function') {
          setTimeout(function () { try { callback(true); } catch (e) { /* ignore */ } }, 0);
        }
      },

      sendData: function (data) { log.popupCalls.push({ name: 'sendData', arg: String(data), ts: Date.now() }); },
      openLink: function (url) { log.popupCalls.push({ name: 'openLink', arg: String(url), ts: Date.now() }); },
      openTelegramLink: function (url) { log.popupCalls.push({ name: 'openTelegramLink', arg: String(url), ts: Date.now() }); },
      switchInlineQuery: function (q) { log.popupCalls.push({ name: 'switchInlineQuery', arg: String(q), ts: Date.now() }); },
      shareToStory: function () { log.popupCalls.push({ name: 'shareToStory', ts: Date.now() }); },
      requestWriteAccess: function (cb) { log.popupCalls.push({ name: 'requestWriteAccess', ts: Date.now() }); },
      requestContact: function (cb) { log.popupCalls.push({ name: 'requestContact', ts: Date.now() }); },
      readTextFromClipboard: function (cb) { log.popupCalls.push({ name: 'readTextFromClipboard', ts: Date.now() }); },
      showScanQrPopup: function (params, cb) { log.popupCalls.push({ name: 'showScanQrPopup', ts: Date.now() }); },
      closeScanQrPopup: function () { log.popupCalls.push({ name: 'closeScanQrPopup', ts: Date.now() }); },
      setHeaderColor: function (c) { log.popupCalls.push({ name: 'setHeaderColor', arg: String(c), ts: Date.now() }); },
      setBackgroundColor: function (c) { log.popupCalls.push({ name: 'setBackgroundColor', arg: String(c), ts: Date.now() }); },
      setBottomBarColor: function (c) { log.popupCalls.push({ name: 'setBottomBarColor', arg: String(c), ts: Date.now() }); },
      enableClosingConfirmation: function () { log.popupCalls.push({ name: 'enableClosingConfirmation', ts: Date.now() }); },
      disableClosingConfirmation: function () { log.popupCalls.push({ name: 'disableClosingConfirmation', ts: Date.now() }); },
      enableVerticalSwipes: function () { log.popupCalls.push({ name: 'enableVerticalSwipes', ts: Date.now() }); },
      disableVerticalSwipes: function () { log.popupCalls.push({ name: 'disableVerticalSwipes', ts: Date.now() }); },

      BackButton: makeButtonManager('BackButton'),
      MainButton: makeButtonManager('MainButton'),
      SecondaryButton: makeButtonManager('SecondaryButton'),
      SettingsButton: makeButtonManager('SettingsButton'),

      HapticFeedback: {
        impactOccurred: function (style) {
          log.hapticCalls.push({ type: 'impactOccurred', style: String(style), ts: Date.now() });
        },
        notificationOccurred: function (type) {
          log.hapticCalls.push({ type: 'notificationOccurred', style: String(type), ts: Date.now() });
        },
        selectionChanged: function () {
          log.hapticCalls.push({ type: 'selectionChanged', ts: Date.now() });
        }
      },

      LocationButton: {
        show: function () {
          log.locationRequests.push({ action: 'show', ts: Date.now() });
          if (cfg.autoLocation) scheduleLocation(cfg.autoLocation);
        },
        hide: function () {
          log.locationRequests.push({ action: 'hide', ts: Date.now() });
        },
        requestLocation: function () {
          log.locationRequests.push({ action: 'requestLocation', ts: Date.now() });
          if (cfg.autoLocation) {
            scheduleLocation(cfg.autoLocation);
            return Promise.resolve({ latitude: cfg.autoLocation[0], longitude: cfg.autoLocation[1] });
          }
          return Promise.reject(new Error('__tma_mock__: autoLocation not configured'));
        }
      }
    };
    return webApp;
  }

  function patch() {
    // Self-healing: if a real SDK (TMA-Studio iframe, telegram-web-app.js, …)
    // later overwrites window.Telegram, keep a reference to it and re-inject
    // only the MISSING methods, re-attaching our evidence log.
    var tg = window.Telegram = window.Telegram || {};
    if (!tg.WebApp) tg.WebApp = {};
    var w = tg.WebApp;
    if (!w.__tmaMockVersion) w.__tmaMockVersion = MOCK_VERSION;
    w.__tmaMockLog = log;
    var mock = makeWebApp();
    for (var k in mock) {
      if (typeof w[k] === 'undefined') w[k] = mock[k];
    }
    // Stable evidence + control surface, independent of the WebApp object.
    window.__TMA_MOCK__ = log;
    window.__TMA_MOCK_VERSION__ = MOCK_VERSION;
    window.__tmaEmit = emit;
    window.__tmaPatch = patch;
  }

  patch();
  // Re-patch after the app/DOM settles and at a few later moments so a
  // late-arriving real SDK gets our missing methods merged in.
  var delays = [0, 500, 1500, 3000, 6000];
  for (var i = 1; i < delays.length; i++) {
    setTimeout(patch, delays[i]);
  }
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', function () { setTimeout(patch, 0); });
  }
  window.addEventListener('load', function () { setTimeout(patch, 0); });
})();
"""


def _initdata_hash(bot_token: str | None, data_check_string: str) -> str:
    """initData ``hash`` field.

    With a real bot token: exactly what Telegram's backend computes —
    ``HMAC_SHA256(secret=HMAC_SHA256(key="WebAppData", msg=bot_token),
    msg=data_check_string)``. Without a token: a deterministic FAKE hash
    (SHA-256 of the data string) — clearly marked, never presented as real.
    """
    if bot_token:
        secret = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
        return hmac.new(secret, data_check_string.encode(), hashlib.sha256).hexdigest()
    return hashlib.sha256(("tma-mock-fake:" + data_check_string).encode()).hexdigest()


def build_mock_js(
    *,
    user_id: int = DEFAULT_USER_ID,
    first_name: str = DEFAULT_FIRST_NAME,
    username: str = DEFAULT_USERNAME,
    platform: str = DEFAULT_PLATFORM,
    version: str = DEFAULT_VERSION,
    color_scheme: str = DEFAULT_COLOR_SCHEME,
    bot_token: str | None = None,
    app_name: str = "terramon",
    auto_location: tuple[float, float] | None = None,
    invoice_status: str | None = None,
    mock_version: str = MOCK_VERSION,
) -> str:
    """Build the init-script JS string (embeds the given config as JSON)."""
    now = int(time.time())
    user = {
        "id": user_id,
        "first_name": first_name,
        "username": username,
        "language_code": "ru",
        "is_premium": True,
        "allows_write_to_pm": True,
    }
    params: dict[str, str] = {
        "query_id": f"AAH{user_id}X",
        "user": json.dumps(user, separators=(",", ":")),
        "auth_date": str(now),
        "start_param": app_name,
    }
    # Telegram data_check_string: sorted key=value lines, hash excluded.
    data_check_string = "\n".join(
        f"{k}={params[k]}" for k in sorted(params)
    )
    params["hash"] = _initdata_hash(bot_token, data_check_string)
    init_data = urllib.parse.urlencode(params)

    init_data_unsafe: dict = dict(params)
    init_data_unsafe["user"] = user  # parsed form, as the real SDK provides

    cfg = {
        "initData": init_data,
        "initDataUnsafe": init_data_unsafe,
        "platform": platform,
        "version": version,
        "colorScheme": color_scheme,
        "themeParams": {
            "bg_color": "#1c1c1e",
            "text_color": "#ffffff",
            "hint_color": "#8e8e93",
            "link_color": "#6ab3f3",
            "button_color": "#2481cc",
            "button_text_color": "#ffffff",
            "secondary_bg_color": "#2c2c2e",
        },
        "invoiceStatus": invoice_status,
        "autoLocation": list(auto_location) if auto_location else None,
        "initDataSigned": bool(bot_token),
        "mockVersion": mock_version,
    }
    js = _TMA_MOCK_JS.replace("__TMA_MOCK_CONFIG_JSON__", json.dumps(cfg))
    return js


def setup_tma_env(
    page,
    *,
    user_id: int = DEFAULT_USER_ID,
    first_name: str = DEFAULT_FIRST_NAME,
    username: str = DEFAULT_USERNAME,
    platform: str = DEFAULT_PLATFORM,
    bot_token: str | None = None,
    auto_location: tuple[float, float] | None = None,
    invoice_status: str | None = None,
) -> dict:
    """Inject the TMA mock BEFORE the app loads (``page.add_init_script``).

    Must be called before ``page.goto(...)``. Returns a summary dict for the
    KPI report evidence.
    """
    js = build_mock_js(
        user_id=user_id,
        first_name=first_name,
        username=username,
        platform=platform,
        bot_token=bot_token,
        auto_location=auto_location,
        invoice_status=invoice_status,
    )
    page.add_init_script(js)
    return {
        "mode": "injected-mock",
        "platform": platform,
        "version": DEFAULT_VERSION,
        "colorScheme": DEFAULT_COLOR_SCHEME,
        "user_id": user_id,
        "initDataSigned": bool(bot_token),
        "autoLocation": list(auto_location) if auto_location else None,
        "note": (
            "resilient window.Telegram.WebApp mock injected pre-load "
            "(initData + LocationButton + HapticFeedback + openInvoice + "
            "MainButton stubs; every call recorded in window.__TMA_MOCK__)"
        ),
    }


def read_tma_evidence(page) -> dict | None:
    """Read ``window.__TMA_MOCK__`` evidence from the page (None if absent)."""
    try:
        return page.evaluate("window.__TMA_MOCK__ || null")
    except Exception:
        return None


def probe_tma_studio(
    browser,
    app_url: str,
    studio_url: str = TMA_STUDIO_DEFAULT_URL,
) -> dict:
    """Honest attempt to use the TMA-Studio web demo as the TMA host.

    Attempts ``<studio_url>?appUrl=<app_url>`` (the only sensible query
    param for a hosted emulator) and checks whether a REAL (non-mock)
    ``window.Telegram.WebApp`` appears. Verified 2026-08-09 from source
    (repo ``website/``) and a live probe: the pages.dev site is a marketing
    landing page — no emulator, no query-param handling — so this returns
    ``ok=False`` with the reason and the caller falls back to the injected
    mock. The real TMA-Studio is a desktop Electron app (manual GUI setup:
    install → add bot token + app URL → pick platform), which is not
    headless-drivable.
    """
    probe = {
        "attempted": True,
        "studio_url": studio_url,
        "app_url": app_url,
        "ok": False,
        "mode": None,
        "reason": None,
        "detail": None,
    }
    ctx = None
    try:
        ctx = browser.new_context(viewport={"width": 1280, "height": 800})
        page = ctx.new_page()
        candidate = f"{studio_url}?appUrl={urllib.parse.quote(app_url, safe='')}"
        page.goto(candidate, timeout=30000, wait_until="domcontentloaded")
        page.wait_for_timeout(4000)
        probe["detail"] = {
            "title": page.title(),
            "body_snippet": page.locator("body").inner_text()[:200],
        }
        has_real = page.evaluate(
            "!!(window.Telegram && window.Telegram.WebApp "
            "&& !window.Telegram.WebApp.__tmaMockVersion)"
        )
        if has_real:
            probe["ok"] = True
            probe["mode"] = "tma-studio-real"
        else:
            probe["reason"] = (
                "tma-studio.pages.dev serves a marketing landing page "
                "(no emulator, no ?appUrl= handling — verified from repo "
                "website/ source and live probe); the real emulator is a "
                "desktop Electron app needing manual GUI setup"
            )
    except Exception as e:  # network down, DNS, timeout, ...
        probe["reason"] = f"tma-studio probe failed: {str(e)[:200]}"
    finally:
        if ctx is not None:
            try:
                ctx.close()
            except Exception:
                pass
    if probe["mode"] is None:
        probe["mode"] = "mock-fallback"
    return probe
