# -*- coding: utf-8 -*-
"""
Dispatch guard — an OPT-IN PreToolUse hook (silent unless TLOR_DISPATCH_GUARD=1).

Unconditionally denies Agent/Task dispatches whose subagent_type is a generic
escape hatch ("general-purpose" or "claude") or a built-in shadowed type
("plan" or "explore"). agents/Explore.md is only a backup for sessions where
this guard is off. The named "bombadil-freeagent" type is allowed only with a
case-insensitive "no-role-fits" reason in its prompt; the role now pins
`model: sonnet` / `effort: medium` in its own frontmatter, so an explicit
`model` on the dispatch is an optional per-call override, not a requirement.
This is the L2 backstop for dispatch.md §3: naming slips that bypass the pinned
role table get redirected instead of silently going through.

Fails open on any error — the guard must never break a session.
"""
import json
import os
import sys

if os.environ.get("TLOR_DISPATCH_GUARD") != "1":
    sys.exit(0)

UNCONDITIONALLY_DENIED_TYPES = frozenset({
    "general-purpose", "claude", "plan", "explore",
})


def main():
    try:
        data = json.loads(sys.stdin.read() or "{}")
        tool_name = data.get("tool_name", "")
        tool_input = data.get("tool_input", {}) or {}

        # Only guard Agent/Task dispatches
        if tool_name not in ("Agent", "Task"):
            return 0

        subagent_type = (tool_input.get("subagent_type", "") or "").strip().lower()

        # Not a guarded type (including missing/"" — harness default)
        if subagent_type == "bombadil-freeagent":
            prompt = tool_input.get("prompt", "") or ""
            if isinstance(prompt, str) and "no-role-fits" in prompt.lower():
                return 0
            deny_reason = (
                "tlor dispatch_guard: bombadil-freeagent requires a "
                "'no-role-fits reason: ...' line in the prompt. (model is "
                "pinned to sonnet/medium by the role's own frontmatter; an "
                "explicit `model` on the dispatch is an optional override, "
                "not a requirement.)"
            )
        elif subagent_type == "explore":
            deny_reason = (
                "tlor dispatch_guard: built-in Explore is denied. Search -> "
                "rohirrim-outrider (targeted) / ranger-pathfinder (broad). "
                "agents/Explore.md is only a backup for sessions where this "
                "guard is off."
            )
        elif subagent_type not in UNCONDITIONALLY_DENIED_TYPES:
            return 0
        elif subagent_type == "plan":
            deny_reason = (
                "tlor dispatch_guard: built-in Plan is banned (user rule "
                "2026-08-14); design stays with the Maia or a role per "
                "dispatch.md §3. Built-in Explore is also denied. ONLY if the "
                "task needs tools/MCP permissions no tlor role has, dispatch "
                "to subagent_type "
                "\"bombadil-freeagent\" instead, with a 'no-role-fits "
                "reason: ...' line in the prompt."
            )
        else:
            deny_reason = (
                "tlor dispatch_guard: subagent_type '" + subagent_type + "' "
                "bypasses the pinned role table (dispatch.md §3). Use the "
                "matching role — verification→eagle-sentinel, "
                "implement→gondor-builder/dwarf-smith, repo search→"
                "rohirrim-outrider/ranger-pathfinder, web research→"
                "noldor-loremaster. If a generic agent is truly required, "
                "dispatch to subagent_type \"bombadil-freeagent\" instead, with "
                "a 'no-role-fits reason: ...' line in the prompt. "
                "(bombadil-freeagent is the free agent outside the roster "
                "— for task shapes no pinned role covers.)"
            )

        print(json.dumps({
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": deny_reason,
            }
        }, ensure_ascii=False))
    except Exception:
        pass  # fail-open: guard failure must never block a session
    return 0


if __name__ == "__main__":
    sys.exit(main())
