# -*- coding: utf-8 -*-
"""Black-box tests for hooks/stdd_test_guard.py."""
from conftest import HOOKS_DIR

SCRIPT = HOOKS_DIR / "stdd_test_guard.py"

TASKS_MD = """\
- [wip] Implement feature X
  Test file: `tests/test_wip_thing.py`

- [ ] Implement feature Y
  Test file: `tests/test_other_thing.py`
"""


def _payload(file_path, cwd, tool_name="Edit"):
    return {
        "tool_name": tool_name,
        "tool_input": {"file_path": file_path},
        "cwd": cwd,
    }


def _make_tasks_md(tmp_path):
    change_dir = tmp_path / "STDD" / "some-change"
    change_dir.mkdir(parents=True)
    tasks_md = change_dir / "tasks.md"
    tasks_md.write_text(TASKS_MD, encoding="utf-8")
    return tmp_path


def test_wip_test_file_is_denied(run_hook, tmp_path):
    cwd = _make_tasks_md(tmp_path)
    result = run_hook(
        SCRIPT,
        _payload(str(cwd / "tests" / "test_wip_thing.py"), str(cwd)),
    )
    assert result.returncode == 0
    decision = result.decision
    assert decision is not None
    assert decision["hookSpecificOutput"]["permissionDecision"] == "deny"


def test_non_wip_test_file_is_allowed(run_hook, tmp_path):
    cwd = _make_tasks_md(tmp_path)
    result = run_hook(
        SCRIPT,
        _payload(str(cwd / "tests" / "test_other_thing.py"), str(cwd)),
    )
    assert result.returncode == 0
    assert result.decision is None


def test_allow_test_rewrite_env_bypasses_deny(run_hook, tmp_path):
    cwd = _make_tasks_md(tmp_path)
    result = run_hook(
        SCRIPT,
        _payload(str(cwd / "tests" / "test_wip_thing.py"), str(cwd)),
        env_overrides={"TLOR_STDD_ALLOW_TEST_REWRITE": "1"},
    )
    assert result.returncode == 0
    assert result.decision is None


def test_no_tasks_md_allows(run_hook, tmp_path):
    result = run_hook(
        SCRIPT,
        _payload(str(tmp_path / "tests" / "test_wip_thing.py"), str(tmp_path)),
    )
    assert result.returncode == 0
    assert result.decision is None


def test_malformed_stdin_fails_open(run_hook, tmp_path):
    result = run_hook(
        SCRIPT,
        "not json",
        cwd=str(tmp_path),
    )
    assert result.returncode == 0
    assert result.decision is None
