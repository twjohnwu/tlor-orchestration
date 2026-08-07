# -*- coding: utf-8 -*-
"""
Dispatch guard — an OPT-IN PreToolUse hook (silent unless TLOR_DISPATCH_GUARD=1).

Denies Agent/Task dispatches whose subagent_type is a generic escape hatch
("general-purpose" or "claude") unless the prompt carries the literal marker
"[bombadil-freeagent]" AND an explicit `model` parameter is passed. This is the L2
backstop for dispatch.md §3: naming slips that bypass the pinned role table
get redirected instead of silently going through.

Fails open on any error — the guard must never break a session.
"""
import json
import os
import sys

if os.environ.get("TLOR_DISPATCH_GUARD") != "1":
    sys.exit(0)

GENERIC_SUBAGENT_TYPES = frozenset({"general-purpose", "claude"})

GENERIC_OK_MARKER = "[bombadil-freeagent]"


def main():
    try:
        data = json.loads(sys.stdin.read() or "{}")
        tool_name = data.get("tool_name", "")
        tool_input = data.get("tool_input", {}) or {}

        # Only guard Agent/Task dispatches
        if tool_name not in ("Agent", "Task"):
            return 0

        subagent_type = (tool_input.get("subagent_type", "") or "").lower()

        # Not a generic escape hatch (including missing/"" — harness default)
        if subagent_type not in GENERIC_SUBAGENT_TYPES:
            return 0

        prompt = tool_input.get("prompt", "") or ""
        model = tool_input.get("model")

        if GENERIC_OK_MARKER in prompt and isinstance(model, str) and model:
            return 0

        # Generic dispatch with no opt-out marker/model → deny
        print(json.dumps({
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": (
                    "tlor dispatch_guard: subagent_type '" + subagent_type + "' "
                    "bypasses the pinned role table (dispatch.md §3). Use the "
                    "matching role — verification→eagle-sentinel, "
                    "implement→gondor-builder/dwarf-smith, repo search→"
                    "rohirrim-outrider/ranger-pathfinder, web research→"
                    "noldor-loremaster. If a generic agent is truly required, "
                    "add the marker [bombadil-freeagent] to the prompt AND pass an "
                    "explicit model. ([bombadil-freeagent] marks the free agent "
                    "outside the roster — for task shapes no pinned role covers.)"
                ),
            }
        }, ensure_ascii=False))
    except Exception:
        pass  # fail-open: guard failure must never block a session
    return 0


if __name__ == "__main__":
    sys.exit(main())
