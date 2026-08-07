#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────
# Terramon Ops Layer — lesson 9 (Terminal & Shell) applied
# Aliases + tmux session + health monitor for the live game.
# Source from ~/.bashrc:  source scripts/terramon_ops.sh
# ─────────────────────────────────────────────────────────────

# ── URLs (edit if the Railway domain changes) ──
export TERRAMON_URL="${TERRAMON_URL:-https://terramon-tma-production.up.railway.app}"

# ── Health check: HTTP code + creature presence in one shot ──
tstatus() {
  code=$(curl -s -o /dev/null -w '%{http_code}' --max-time 12 "$TERRAMON_URL/")
  creatures=$(curl -s --max-time 12 "$TERRAMON_URL/" | grep -oiE 'creature' | wc -l)
  echo "HTTP $code | 'creature' on page: $creatures"
  [ "$code" = "200" ] && [ "$creatures" -gt 0 ] && echo "✅ TERRAMON ALIVE" || echo "❌ TERRAMON DOWN"
}

# ── Watch health every N seconds (default 30, lesson 9: watch -n) ──
twatch() {
  local sec="${1:-30}"
  watch -n "$sec" "curl -s -o /dev/null -w 'HTTP %{http_code}' --max-time 10 '$TERRAMON_URL/'; echo; curl -s --max-time 10 '$TERRAMON_URL/' | grep -oiE 'creature' | wc -l | xargs echo 'creature refs:'"
}

# ── Railway log tail (signal only: errors/warnings/tracebacks) ──
tlogs() {
  railway logs --deployment 2>/dev/null | grep -E "ERROR|WARNING|Traceback|NameError|not set" || echo "(no signal lines — clean or railway CLI not authed)"
}

# ── tmux ops session: 3 panes (log watch / health poll / shell) ──
topssession() {
  if ! command -v tmux >/dev/null; then echo "tmux not installed — sudo apt install tmux"; return 1; fi
  local name="terramon"
  if tmux has-session -t "$name" 2>/dev/null; then
    echo "session '$name' exists — tmux attach -t $name"
    return 0
  fi
  tmux new-session -d -s "$name" -x 220 -y 50
  # Pane 1: live health polling
  tmux send-keys -t "$name" "while true; do curl -s -o /dev/null -w '%H:%M:%S HTTP %{http_code}\n' --max-time 10 '$TERRAMON_URL/'; sleep 30; done" Enter
  # Pane 2 (right): railway signal log
  tmux split-window -h -t "$name"
  tmux send-keys -t "$name" "while true; do railway logs --deployment 2>/dev/null | grep -E 'ERROR|WARNING|Traceback|NameError' | tail -5; sleep 60; done" Enter
  # Pane 3 (bottom): free shell
  tmux split-window -v -t "$name"
  tmux send-keys -t "$name" "cd ~/Terramon && echo 'Terramon repo ready — tstatus for health'" Enter
  tmux select-pane -t "$name".3
  echo "✅ tmux session '$name' started — attach: tmux attach -t $name | detach: Ctrl+B D"
}

# ── Post-deploy verification (lesson 9: grep before trust) ──
tverify() {
  echo "1) git:"; git -C ~/Terramon log --oneline -1 2>/dev/null || echo "   (repo not cloned locally)"
  echo "2) HTTP:"; curl -s -o /dev/null -w "   %{http_code}\n" --max-time 12 "$TERRAMON_URL/"
  echo "3) creature markers:"; curl -s --max-time 12 "$TERRAMON_URL/" | grep -oiE 'creature' | wc -l | xargs echo "   count:"
}

# ── Quick help ──
thelp() {
  echo "tstatus     — HTTP code + creature check (one-shot)"
  echo "twatch [N]  — health poll every N sec (default 30)"
  echo "tlogs       — railway logs, signal lines only"
  echo "topssession — 3-pane tmux ops session"
  echo "tverify     — post-deploy verification (git+HTTP+creature)"
  echo "thelp       — this help"
}
