# -*- coding: utf-8 -*-
"""Shared deny-path matrix for institution_guard.py and institution_guard.sh.

Kept in one place so the .py and .sh test suites exercise the exact same
cases (dispatch.md §2: enumerate every violation class, positive AND
negative forms).
"""


def deny_cases(home):
    """(label, file_path) pairs that MUST be denied for a main-session Edit."""
    return [
        ("institution_real_path", f"{home}/.claude/institution/rules/x.md"),
        ("rules_alias", f"{home}/.claude/rules/x.md"),
        ("agents_alias", f"{home}/.claude/agents/x.md"),
        ("agent_doc_alias", f"{home}/.claude/agent_doc/x.md"),
        ("claude_md_arbitrary_location", "/some/project/CLAUDE.md"),
        ("agents_md_arbitrary_location", "/some/project/AGENTS.md"),
        ("claude_md_bare", "CLAUDE.md"),
        ("agents_md_bare", "AGENTS.md"),
    ]


def allow_cases(home):
    """(label, file_path) pairs that must NOT be denied (outside guarded scope)."""
    return [
        ("unrelated_path", f"{home}/Desktop/notes.txt"),
        ("unrelated_home_claude_subdir", f"{home}/.claude/projects/foo.md"),
        ("claude_md_backup_suffix", "/some/project/CLAUDE.md.bak"),
        ("claude_mdx_suffix", "/some/project/CLAUDE.mdx"),
    ]
