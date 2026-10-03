# -*- coding: utf-8 -*-
"""
Dispatch guard — an OPT-IN PreToolUse hook (silent unless TLOR_DISPATCH_GUARD=1).

Unconditionally denies Agent/Task dispatches whose subagent_type is a generic
escape hatch ("general-purpose" or "claude") or the built-in Plan type
("plan"). Built-in Explore (any case) is allowed ONLY when a tlor mirror
(agents/Explore.md, a copy of ranger-pathfinder under that name) is installed
at <cwd>/.claude/agents/Explore.md or ~/.claude/agents/Explore.md (TLOR_HOME
overrides ~ for tests); otherwise plain Explore is the unpinned built-in
(plugin-route installs namespace it as tlor:Explore) and is denied. The named "bombadil-freeagent" type is allowed only
with a case-insensitive "no-role-fits" reason in its prompt; the role now
pins `model: sonnet` / `effort: medium` in its own frontmatter, so an
explicit `model` on the dispatch is an optional per-call override, not a
requirement. This is the L2 backstop for dispatch.md §3: naming slips that
bypass the pinned role table get redirected instead of silently going through.

Fails open on any error — the guard must never break a session.
"""
import json
import os
import sys
from pathlib import Path

if os.environ.get("TLOR_DISPATCH_GUARD") != "1":
    sys.exit(0)

GENERIC_SUBAGENT_TYPES = frozenset({"general-purpose", "claude"})
BUILTIN_SHADOWED_TYPES = frozenset({"plan"})
MIRRORED_TYPES = frozenset({"explore"})


def _mirror_installed(data):
    """True when a tlor mirror file shadows the built-in agent (project > user)."""
    cwd = Path(data.get("cwd") or os.getcwd())
    home = Path(os.environ.get("TLOR_HOME") or Path.home())
    return any(
        (base / ".claude" / "agents" / "Explore.md").exists() for base in (cwd, home)
    )


def main():
    try:
        data = json.loads(sys.stdin.read() or "{}")
        tool_name = data.get("tool_name", "")
        tool_input = data.get("tool_input", {}) or {}

        # Only guard Agent/Task dispatches
        if tool_name not in ("Agent", "Task"):
            return 0

        subagent_type = (tool_input.get("subagent_type", "") or "").lower()

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
        elif subagent_type in MIRRORED_TYPES:
            if _mirror_installed(data):
                return 0
            deny_reason = (
                "tlor dispatch_guard: built-in Explore is denied here because "
                "no tlor mirror is installed (`~/.claude/agents/Explore.md` or "
                "`<cwd>/.claude/agents/Explore.md`); plugin-route installs "
                "namespace it as `tlor:Explore`. Search → rohirrim-outrider / "
                "ranger-pathfinder (or `tlor:Explore`). Design stays with the "
                "Maia or a role per dispatch.md §3. ONLY if the task needs "
                "tools/MCP permissions no tlor role has, dispatch to "
                "subagent_type \"bombadil-freeagent\" instead, with a "
                "'no-role-fits reason: ...' line in the prompt."
            )
        elif subagent_type not in GENERIC_SUBAGENT_TYPES | BUILTIN_SHADOWED_TYPES:
            return 0
        elif subagent_type in BUILTIN_SHADOWED_TYPES:
            deny_reason = (
                "tlor dispatch_guard: built-in Plan is banned (user rule "
                "2026-08-14); design stays with the Maia or a role per "
                "dispatch.md §3. Built-in Explore is allowed only when the tlor "
                "mirror is installed. ONLY if the task needs tools/MCP permissions "
                "no tlor role has, dispatch to subagent_type "
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
