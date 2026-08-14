# -*- coding: utf-8 -*-
"""Black-box tests for hooks/dispatch_guard.py.

Opt-in PreToolUse hook (TLOR_DISPATCH_GUARD=1): denies Agent/Task dispatches
whose subagent_type is a guarded escape hatch (including built-in types)
unless the prompt carries the literal marker "[bombadil-freeagent]" AND an
explicit `model` parameter is passed.
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
    result = _run(run_hook, _payload(subagent_type="general-purpose", prompt="do it [bombadil-freeagent]"))
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
    result = _run(run_hook, _payload(subagent_type="general-purpose", prompt="do it [bombadil-freeagent]", model="opus"))
    assert result.returncode == 0
    assert result.decision is None


def test_old_marker_no_longer_recognized_denied(run_hook):
    result = _run(run_hook, _payload(subagent_type="general-purpose", prompt="do it [generic-ok]", model="opus"))
    assert result.returncode == 0
    decision = result.decision
    assert decision is not None
    assert decision["hookSpecificOutput"]["permissionDecision"] == "deny"


def test_claude_type_denied(run_hook):
    result = _run(run_hook, _payload(subagent_type="claude"))
    assert result.returncode == 0
    decision = result.decision
    assert decision is not None
    assert decision["hookSpecificOutput"]["permissionDecision"] == "deny"


def test_explore_type_denied(run_hook):
    result = _run(run_hook, _payload(subagent_type="Explore"))
    assert result.returncode == 0
    decision = result.decision
    assert decision is not None
    assert decision["hookSpecificOutput"]["permissionDecision"] == "deny"


def test_explore_lowercase_denied(run_hook):
    result = _run(run_hook, _payload(subagent_type="explore"))
    assert result.returncode == 0
    decision = result.decision
    assert decision is not None
    assert decision["hookSpecificOutput"]["permissionDecision"] == "deny"


def test_plan_type_denied(run_hook):
    result = _run(run_hook, _payload(subagent_type="Plan"))
    assert result.returncode == 0
    decision = result.decision
    assert decision is not None
    assert decision["hookSpecificOutput"]["permissionDecision"] == "deny"


def test_explore_marker_and_model_allowed(run_hook):
    result = _run(run_hook, _payload(subagent_type="explore", prompt="do it [bombadil-freeagent]", model="sonnet"))
    assert result.returncode == 0
    assert result.decision is None


def test_plan_marker_and_model_allowed(run_hook):
    result = _run(run_hook, _payload(subagent_type="plan", prompt="do it [bombadil-freeagent]", model="sonnet"))
    assert result.returncode == 0
    assert result.decision is None


def test_explore_fake_marker_denied(run_hook):
    result = _run(run_hook, _payload(subagent_type="explore", prompt="do it [generic]", model="sonnet"))
    assert result.returncode == 0
    decision = result.decision
    assert decision is not None
    assert decision["hookSpecificOutput"]["permissionDecision"] == "deny"


def test_explore_marker_no_model_denied(run_hook):
    result = _run(run_hook, _payload(subagent_type="explore", prompt="do it [bombadil-freeagent]"))
    assert result.returncode == 0
    decision = result.decision
    assert decision is not None
    assert decision["hookSpecificOutput"]["permissionDecision"] == "deny"


def test_explore_deny_reason_mentions_roles_and_escape(run_hook):
    result = _run(run_hook, _payload(subagent_type="explore"))
    assert result.returncode == 0
    decision = result.decision
    assert decision is not None
    reason = decision["hookSpecificOutput"]["permissionDecisionReason"]
    assert "rohirrim-outrider" in reason
    assert "ranger-pathfinder" in reason
    assert "[bombadil-freeagent]" in reason


def test_plan_deny_reason_mentions_roles_and_escape(run_hook):
    result = _run(run_hook, _payload(subagent_type="Plan"))
    assert result.returncode == 0
    decision = result.decision
    assert decision is not None
    reason = decision["hookSpecificOutput"]["permissionDecisionReason"]
    assert "rohirrim-outrider" in reason
    assert "ranger-pathfinder" in reason
    assert "[bombadil-freeagent]" in reason


def test_malformed_stdin_fails_open(run_hook):
    result = run_hook(SCRIPT, "{not valid json", env_overrides={"TLOR_DISPATCH_GUARD": "1"})
    assert result.returncode == 0
    assert result.decision is None


def test_missing_subagent_type_allowed(run_hook):
    result = _run(run_hook, _payload(subagent_type=None))
    assert result.returncode == 0
    assert result.decision is None
