# -*- coding: utf-8 -*-
"""
Institution guard — an OPT-IN PreToolUse hook (silent unless TLOR_INSTITUTION_GUARD=1).

Blocks the main session from directly editing institution files: everything
under ~/.claude/institution/ (rules, agents, hooks — real paths), the
~/.claude/rules/ and ~/.claude/agents/ symlink aliases, and CLAUDE.md /
AGENTS.md router files anywhere. These edits must be dispatched to a
subagent per dispatch.md §1. Subagent calls (identified by agent_id) are
allowed through. Project-level .claude/rules|agents dirs outside the home
~/.claude are intentionally NOT matched (installer default: home-level only).
Fails open on any error — the guard must never break a session.
"""
import json
import os
import sys

if os.environ.get("TLOR_INSTITUTION_GUARD") != "1":
    sys.exit(0)

HOME = os.path.expanduser("~")

INSTITUTION_PREFIXES = (
    HOME + "/.claude/institution/",  # real paths: rules/, agents/, hooks/, ...
    HOME + "/.claude/rules/",        # symlink alias
    HOME + "/.claude/agents/",       # symlink alias
)

ROUTER_FILE_PATTERNS = (
    "/CLAUDE.md",
    "/AGENTS.md",
)


def is_institution_file(path):
    """Check if a file path is a guarded institution file."""
    if not path:
        return False
    # Exact filename match for root-level files
    if path == "CLAUDE.md" or path == "AGENTS.md":
        return True
    # Home-anchored institution tree (real paths and symlink aliases)
    for prefix in INSTITUTION_PREFIXES:
        if path.startswith(prefix):
            return True
    # Router files, any location (anchored: matches the shell's
    # */CLAUDE.md|CLAUDE.md|*/AGENTS.md|AGENTS.md glob, not a substring
    # anywhere in the path — e.g. CLAUDE.md.bak / CLAUDE.mdx must NOT match)
    for pattern in ROUTER_FILE_PATTERNS:
        if path.endswith(pattern):
            return True
    return False


def main():
    try:
        data = json.loads(sys.stdin.read() or "{}")
        tool_name = data.get("tool_name", "")
        tool_input = data.get("tool_input", {}) or {}
        agent_id = data.get("agent_id", "")

        # Only guard write operations
        if tool_name not in ("Edit", "Write", "NotebookEdit"):
            return 0

        file_path = tool_input.get("file_path", "") or tool_input.get("notebook_path", "")

        # Only guard institution files
        if not is_institution_file(file_path):
            return 0

        # Subagents (with agent_id) are allowed
        if agent_id:
            return 0

        # Main session trying to edit institution file → deny
        print(json.dumps({
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": (
                    "Institution file: the main session must not edit "
                    "~/.claude institution files (rules/agents/hooks) or "
                    "CLAUDE.md/AGENTS.md inline. Author the full new text "
                    "as a recipe and dispatch it to a subagent "
                    "(dispatch.md §1). This does not block dispatched "
                    "subagents."
                ),
            }
        }, ensure_ascii=False))
    except Exception:
        pass  # fail-open: guard failure must never block a session
    return 0


if __name__ == "__main__":
    sys.exit(main())
