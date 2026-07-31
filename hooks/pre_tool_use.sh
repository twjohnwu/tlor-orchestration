#!/usr/bin/env bash
# pre_tool_use.sh — thin wrapper chaining the institution_guard and
# dispatch_guard PreToolUse hooks. Detects python3 and dispatches to the
# appropriate implementation. Fail-open: if neither python3 nor bash
# fallback works, exit 0.
# dispatch_guard.py requires Python 3 — it has no bash fallback, mirroring
# its "Requires Python 3" install note; when python3 is absent only
# institution_guard.sh runs.
HOOK_DIR="$(cd "$(dirname "$0")" && pwd)"
STDIN_DATA="$(cat)"
if command -v python3 >/dev/null 2>&1; then
  OUT="$(printf '%s' "$STDIN_DATA" | python3 "$HOOK_DIR/institution_guard.py")"
  if [ -n "$OUT" ]; then
    printf '%s\n' "$OUT"
    exit 0
  fi
  printf '%s' "$STDIN_DATA" | python3 "$HOOK_DIR/dispatch_guard.py"
else
  printf '%s' "$STDIN_DATA" | bash "$HOOK_DIR/institution_guard.sh"
fi
