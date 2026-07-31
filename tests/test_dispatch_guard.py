# -*- coding: utf-8 -*-
"""Black-box tests for hooks/dispatch_guard.py.

Opt-in PreToolUse hook (TLOR_DISPATCH_GUARD=1): denies Agent/Task dispatches
whose subagent_type is a generic escape hatch ("general-purpose" or "claude")
unless the prompt carries the literal marker "[generic-ok]" AND an explicit
`model` parameter is passed.
"""
from conftest import HOOKS_DIR

SCRIPT = HOOKS_DIR / "dispatch_guard.py"


def _payload(subagent_type=None, prompt="", model=None, tool_name="Agent"):
    tool_input = {}
    if subagent_type is not None:
        tool_input["subagent_type"] = subagent_type
    tool_input["prompt"] = prompt
    if model is not None:
        tool_input["model"] = model
    return {"tool_name": tool_name, "tool_input": tool_input}


def _run(run_hook, payload, guard_on=True):
    env_overrides = {"TLOR_DISPATCH_GUARD": "1"} if guard_on else {"TLOR_DISPATCH_GUARD": ""}
    return run_hook(SCRIPT, payload, env_overrides=env_overrides)


def test_env_gate_off_allows(run_hook):
    result = _run(run_hook, _payload(subagent_type="general-purpose"), guard_on=False)
    assert result.returncode == 0
    assert result.decision is None


def test_non_agent_tool_allowed(run_hook):
    result = _run(run_hook, _payload(subagent_type="general-purpose", tool_name="Edit"))
    assert result.returncode == 0
    assert result.decision is None


def test_role_subagent_type_allowed(run_hook):
    result = _run(run_hook, _payload(subagent_type="gondor-builder"))
    assert result.returncode == 0
    assert result.decision is None


def test_general_purpose_no_marker_denied(run_hook):
    result = _run(run_hook, _payload(subagent_type="general-purpose"))
    assert result.returncode == 0
    decision = result.decision
    assert decision is not None
    assert decision["hookSpecificOutput"]["permissionDecision"] == "deny"


def test_marker_but_no_model_denied(run_hook):
    result = _run(run_hook, _payload(subagent_type="general-purpose", prompt="do it [generic-ok]"))
    assert result.returncode == 0
    decision = result.decision
    assert decision is not None
    assert decision["hookSpecificOutput"]["permissionDecision"] == "deny"


def test_model_but_no_marker_denied(run_hook):
    result = _run(run_hook, _payload(subagent_type="general-purpose", prompt="do it", model="opus"))
    assert result.returncode == 0
    decision = result.decision
    assert decision is not None
    assert decision["hookSpecificOutput"]["permissionDecision"] == "deny"


def test_marker_and_model_allowed(run_hook):
    result = _run(run_hook, _payload(subagent_type="general-purpose", prompt="do it [generic-ok]", model="opus"))
    assert result.returncode == 0
    assert result.decision is None


def test_claude_type_denied(run_hook):
    result = _run(run_hook, _payload(subagent_type="claude"))
    assert result.returncode == 0
    decision = result.decision
    assert decision is not None
    assert decision["hookSpecificOutput"]["permissionDecision"] == "deny"


def test_malformed_stdin_fails_open(run_hook):
    result = run_hook(SCRIPT, "{not valid json", env_overrides={"TLOR_DISPATCH_GUARD": "1"})
    assert result.returncode == 0
    assert result.decision is None


def test_missing_subagent_type_allowed(run_hook):
    result = _run(run_hook, _payload(subagent_type=None))
    assert result.returncode == 0
    assert result.decision is None
