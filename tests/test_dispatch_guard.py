# -*- coding: utf-8 -*-
"""Black-box tests for hooks/dispatch_guard.py.

Opt-in PreToolUse hook (TLOR_DISPATCH_GUARD=1): denies Agent/Task dispatches
whose generic types and built-in Plan and Explore are unconditionally denied,
even when an Explore.md mirror exists. The named
"bombadil-freeagent" type requires a "no-role-fits" reason in its prompt;
an explicit `model` parameter is an optional per-call override now that the
role pins model/effort in its own frontmatter.
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


def test_general_purpose_marker_and_model_denied(run_hook):
    result = _run(run_hook, _payload(subagent_type="general-purpose", prompt="do it [bombadil-freeagent]", model="opus"))
    assert result.returncode == 0
    decision = result.decision
    assert decision is not None
    assert decision["hookSpecificOutput"]["permissionDecision"] == "deny"


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


def _mirror(root):
    agents = root / ".claude" / "agents"
    agents.mkdir(parents=True)
    (agents / "Explore.md").write_text("---\nname: Explore\n---\n", encoding="utf-8")
    return root


def _explore_run(run_hook, tmp_path, home_has_mirror=False, cwd_has_mirror=False, subagent_type="Explore"):
    home = tmp_path / "home"
    cwd = tmp_path / "proj"
    home.mkdir()
    cwd.mkdir()
    if home_has_mirror:
        _mirror(home)
    if cwd_has_mirror:
        _mirror(cwd)
    payload = _payload(subagent_type=subagent_type)
    payload["cwd"] = str(cwd)
    return run_hook(SCRIPT, payload, env_overrides={"TLOR_DISPATCH_GUARD": "1", "TLOR_HOME": str(home)})


def _assert_explore_denied(run_hook, tmp_path, **kwargs):
    for n, subagent_type in enumerate(("explore", "Explore", "EXPLORE")):
        (tmp_path / str(n)).mkdir()
        result = _explore_run(run_hook, tmp_path / str(n), subagent_type=subagent_type, **kwargs)
        assert result.returncode == 0
        decision = result.decision
        assert decision is not None
        assert decision["hookSpecificOutput"]["permissionDecision"] == "deny"
        reason = decision["hookSpecificOutput"]["permissionDecisionReason"]
        assert "rohirrim-outrider" in reason
        assert "ranger-pathfinder" in reason


def test_explore_denied_when_home_mirror_exists(run_hook, tmp_path):
    _assert_explore_denied(run_hook, tmp_path, home_has_mirror=True)


def test_explore_denied_when_cwd_mirror_exists(run_hook, tmp_path):
    _assert_explore_denied(run_hook, tmp_path, cwd_has_mirror=True)


def test_explore_denied_when_no_mirror_installed(run_hook, tmp_path):
    _assert_explore_denied(run_hook, tmp_path)


def test_explore_with_surrounding_whitespace_denied(run_hook, tmp_path):
    result = _explore_run(run_hook, tmp_path, subagent_type=" explore ")
    assert result.returncode == 0
    decision = result.decision
    assert decision is not None
    assert decision["hookSpecificOutput"]["permissionDecision"] == "deny"
    assert "rohirrim-outrider" in decision["hookSpecificOutput"]["permissionDecisionReason"]


def test_plan_denied_whether_or_not_mirror_exists(run_hook, tmp_path):
    for name, kwargs in (("a", {}), ("b", {"home_has_mirror": True}), ("c", {"cwd_has_mirror": True})):
        (tmp_path / name).mkdir()
        result = _explore_run(run_hook, tmp_path / name, subagent_type="Plan", **kwargs)
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


def test_plan_marker_and_model_denied(run_hook):
    result = _run(run_hook, _payload(subagent_type="plan", prompt="do it [bombadil-freeagent]", model="sonnet"))
    assert result.returncode == 0
    decision = result.decision
    assert decision is not None
    assert decision["hookSpecificOutput"]["permissionDecision"] == "deny"


def test_plan_deny_reason_mentions_plan_and_escape(run_hook):
    result = _run(run_hook, _payload(subagent_type="Plan"))
    assert result.returncode == 0
    decision = result.decision
    assert decision is not None
    reason = decision["hookSpecificOutput"]["permissionDecisionReason"]
    assert "Plan" in reason
    assert "Explore" in reason
    assert "bombadil-freeagent" in reason


def test_bombadil_freeagent_with_model_and_reason_allowed(run_hook):
    result = _run(run_hook, _payload(
        subagent_type="bombadil-freeagent",
        model="opus",
        prompt="no-role-fits reason: web scraping via a custom browser tool",
    ))
    assert result.returncode == 0
    assert result.decision is None


def test_bombadil_freeagent_without_model_allowed_when_reason_present(run_hook):
    result = _run(run_hook, _payload(
        subagent_type="bombadil-freeagent",
        prompt="no-role-fits reason: web scraping via a custom browser tool",
    ))
    assert result.returncode == 0
    assert result.decision is None


def test_bombadil_freeagent_model_without_reason_denied(run_hook):
    result = _run(run_hook, _payload(
        subagent_type="bombadil-freeagent", model="opus", prompt="web scraping via a custom browser tool",
    ))
    assert result.returncode == 0
    decision = result.decision
    assert decision is not None
    assert decision["hookSpecificOutput"]["permissionDecision"] == "deny"


def test_bombadil_freeagent_reason_is_case_insensitive(run_hook):
    result = _run(run_hook, _payload(
        subagent_type="bombadil-freeagent",
        model="opus",
        prompt="No-Role-Fits reason: web scraping via a custom browser tool",
    ))
    assert result.returncode == 0
    assert result.decision is None


def test_malformed_stdin_fails_open(run_hook):
    result = run_hook(SCRIPT, "{not valid json", env_overrides={"TLOR_DISPATCH_GUARD": "1"})
    assert result.returncode == 0
    assert result.decision is None


def test_missing_subagent_type_allowed(run_hook):
    result = _run(run_hook, _payload(subagent_type=None))
    assert result.returncode == 0
    assert result.decision is None
