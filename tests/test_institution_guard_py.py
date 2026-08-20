# -*- coding: utf-8 -*-
"""Black-box tests for hooks/institution_guard.py.

Regression coverage for the symlink-path gap fixed in bc3ca8c: the old
guard only matched the literal substring "/.claude/rules/", so an edit
addressed via the RESOLVED real path (~/.claude/institution/rules/...,
reached through the ~/.claude/rules symlink) evaded it entirely.
"""
import os
import re

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


def test_agent_doc_alias_denied(run_hook, tmp_home):
    """agent_doc/ is a 4th institution symlink alias (like rules/ and
    agents/) — a main-session Edit addressed via the alias path must be
    denied. Now redundant with the shared deny_cases() matrix in
    _institution_guard_cases.py (which also drives
    test_institution_guard_sh.py, now aware of agent_doc/ too) — kept as an
    explicit regression pin for this specific case."""
    result = run_hook(
        SCRIPT,
        _payload(f"{tmp_home}/.claude/agent_doc/x.md"),
        env_overrides={"HOME": str(tmp_home), "TLOR_INSTITUTION_GUARD": "1"},
    )
    assert result.returncode == 0
    decision = result.decision
    assert decision is not None, "expected deny for agent_doc/ alias path"
    assert decision["hookSpecificOutput"]["permissionDecision"] == "deny"


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


# M16 — constants-parity check. Each of these hooks independently defines the
# "which tool_name values count as a write" set; they are deliberately NOT
# extracted into a shared module (do-not-do: keep each hook a single-file,
# stdlib-only script), so a future divergence must fail loudly here instead.
_TOOL_TOKEN_RE = re.compile(r'"(Edit|Write|NotebookEdit|MultiEdit)"')

_STDD_TEST_GUARD = HOOKS_DIR / "stdd_test_guard.py"
_VERIFY_GATE = HOOKS_DIR / "verify_gate.py"
_INSTITUTION_GUARD_SH = HOOKS_DIR / "institution_guard.sh"
_REGISTER_STDD_HOOK = HOOKS_DIR.parent / "hooks" / "register_stdd_hook.py"

EXPECTED_TOOL_SET = frozenset({"Edit", "Write", "NotebookEdit"})


def _tool_set_from_python_tuple_or_set_line(text, anchor):
    """Extract the quoted tool-name tokens from the single line/statement
    containing `anchor` (a substring that uniquely marks the tool-list
    literal in that file)."""
    idx = text.index(anchor)
    # Grab a small window after the anchor — enough to cover the whole
    # tuple/set literal but not the rest of the file.
    window = text[idx:idx + 200]
    tokens = _TOOL_TOKEN_RE.findall(window)
    assert tokens, f"could not find quoted tool-name tokens near {anchor!r}"
    return frozenset(tokens)


def test_write_tool_set_is_consistent_across_hooks():
    """M16: institution_guard.py, stdd_test_guard.py, verify_gate.py,
    institution_guard.sh, and register_stdd_hook.py's registered matcher
    must all agree on the exact set of tool_name values treated as a write
    (currently {Edit, Write, NotebookEdit} — MultiEdit intentionally absent
    from all of them, consistent-by-design)."""
    guard_py_text = SCRIPT.read_text(encoding="utf-8")
    stdd_text = _STDD_TEST_GUARD.read_text(encoding="utf-8")
    verify_text = _VERIFY_GATE.read_text(encoding="utf-8")
    sh_text = _INSTITUTION_GUARD_SH.read_text(encoding="utf-8")
    register_text = _REGISTER_STDD_HOOK.read_text(encoding="utf-8")

    guard_py_set = _tool_set_from_python_tuple_or_set_line(
        guard_py_text, 'tool_name not in ("Edit"'
    )
    stdd_set = _tool_set_from_python_tuple_or_set_line(
        stdd_text, 'tool_name not in ("Edit"'
    )
    verify_set = frozenset(_TOOL_TOKEN_RE.findall(verify_text))
    sh_set = frozenset(re.findall(r"(Edit|Write|NotebookEdit|MultiEdit)", sh_text.split("case \"$tool_name\"")[1].split("esac")[0]))
    matcher_match = re.search(r'"matcher":\s*"([^"]+)"', register_text)
    assert matcher_match, "could not find the registered matcher string"
    register_set = frozenset(matcher_match.group(1).split("|"))

    sets_by_source = {
        "institution_guard.py": guard_py_set,
        "stdd_test_guard.py": stdd_set,
        "verify_gate.py": verify_set,
        "institution_guard.sh": sh_set,
        "register_stdd_hook.py (matcher)": register_set,
    }

    for name, found in sets_by_source.items():
        assert found == EXPECTED_TOOL_SET, (
            f"{name} tool set {sorted(found)} does not match the expected "
            f"agreed set {sorted(EXPECTED_TOOL_SET)}"
        )
