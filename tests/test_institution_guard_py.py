# -*- coding: utf-8 -*-
"""Black-box tests for hooks/institution_guard.py.

Regression coverage for the symlink-path gap fixed in bc3ca8c: the old
guard only matched the literal substring "/.claude/rules/", so an edit
addressed via the RESOLVED real path (~/.claude/institution/rules/...,
reached through the ~/.claude/rules symlink) evaded it entirely.
"""
import os

import pytest

from conftest import HOOKS_DIR
from _institution_guard_cases import allow_cases, deny_cases

SCRIPT = HOOKS_DIR / "institution_guard.py"


def _payload(file_path, tool_name="Edit", agent_id=""):
    return {
        "tool_name": tool_name,
        "tool_input": {"file_path": file_path},
        "agent_id": agent_id,
    }


def test_env_gate_unset_allows_even_institution_path(run_hook, tmp_home):
    env = os.environ.copy()
    env.pop("TLOR_INSTITUTION_GUARD", None)
    result = run_hook(
        SCRIPT,
        _payload(f"{tmp_home}/.claude/institution/rules/x.md"),
        env_overrides={"HOME": str(tmp_home), "TLOR_INSTITUTION_GUARD": ""},
    )
    assert result.returncode == 0
    assert result.decision is None


@pytest.mark.parametrize("label,rel", [(c[0], c[1]) for c in deny_cases("{home}")])
def test_main_session_deny_matrix(run_hook, tmp_home, label, rel):
    file_path = rel.format(home=str(tmp_home)) if "{home}" in rel else rel
    result = run_hook(
        SCRIPT,
        _payload(file_path),
        env_overrides={"HOME": str(tmp_home), "TLOR_INSTITUTION_GUARD": "1"},
    )
    assert result.returncode == 0
    decision = result.decision
    assert decision is not None, f"expected deny for {label} ({file_path})"
    assert decision["hookSpecificOutput"]["permissionDecision"] == "deny"


def test_symlink_regression_resolved_real_path_is_denied(run_hook, tmp_home):
    """The shipped-bug case: a real institution/rules dir plus a ~/.claude/rules
    symlink pointing at it. An edit addressed via the RESOLVED real path must
    be denied by the current (fixed) guard."""
    real_rules_dir = tmp_home / ".claude" / "institution" / "rules"
    real_rules_dir.mkdir(parents=True)
    alias = tmp_home / ".claude" / "rules"
    alias.symlink_to(real_rules_dir, target_is_directory=True)

    resolved_path = os.path.realpath(str(alias / "dispatch.md"))
    assert "institution" in resolved_path  # sanity: this IS the real path, not the alias

    result = run_hook(
        SCRIPT,
        _payload(resolved_path),
        env_overrides={"HOME": str(tmp_home), "TLOR_INSTITUTION_GUARD": "1"},
    )
    decision = result.decision
    assert decision is not None
    assert decision["hookSpecificOutput"]["permissionDecision"] == "deny"


@pytest.mark.parametrize("label,rel", [(c[0], c[1]) for c in allow_cases("{home}")])
def test_unrelated_paths_allowed(run_hook, tmp_home, label, rel):
    file_path = rel.format(home=str(tmp_home))
    result = run_hook(
        SCRIPT,
        _payload(file_path),
        env_overrides={"HOME": str(tmp_home), "TLOR_INSTITUTION_GUARD": "1"},
    )
    assert result.returncode == 0
    assert result.decision is None


def test_subagent_bypasses_deny(run_hook, tmp_home):
    result = run_hook(
        SCRIPT,
        _payload(f"{tmp_home}/.claude/institution/rules/x.md", agent_id="subagent-123"),
        env_overrides={"HOME": str(tmp_home), "TLOR_INSTITUTION_GUARD": "1"},
    )
    assert result.returncode == 0
    assert result.decision is None


def test_non_write_tool_allowed(run_hook, tmp_home):
    result = run_hook(
        SCRIPT,
        _payload(f"{tmp_home}/.claude/institution/rules/x.md", tool_name="Read"),
        env_overrides={"HOME": str(tmp_home), "TLOR_INSTITUTION_GUARD": "1"},
    )
    assert result.returncode == 0
    assert result.decision is None


def test_malformed_stdin_fails_open(run_hook, tmp_home):
    result = run_hook(
        SCRIPT,
        "{not valid json",
        env_overrides={"HOME": str(tmp_home), "TLOR_INSTITUTION_GUARD": "1"},
    )
    assert result.returncode == 0
    assert result.decision is None
