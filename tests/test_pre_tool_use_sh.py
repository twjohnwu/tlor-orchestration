# -*- coding: utf-8 -*-
"""Black-box tests for hooks/pre_tool_use.sh — the dispatcher that picks
python3 (institution_guard.py) when available, else falls back to
institution_guard.sh (bash + jq)."""
import json
import os
import shutil

import pytest

from conftest import HOOKS_DIR, have_jq

SCRIPT = HOOKS_DIR / "pre_tool_use.sh"

# External commands institution_guard.sh + pre_tool_use.sh need once python3
# is hidden from PATH: bash itself is invoked directly by the runner, so
# only these need to be reachable via PATH lookups inside the scripts.
FALLBACK_TOOLS = ["bash", "dirname", "jq", "cat"]


def _payload(file_path, agent_id=""):
    return json.dumps({
        "tool_name": "Edit",
        "tool_input": {"file_path": file_path},
        "agent_id": agent_id,
    })


def _no_python_path(tmp_path):
    """Build a PATH entry containing only symlinks to FALLBACK_TOOLS, with
    no python3 anywhere on it."""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    for tool in FALLBACK_TOOLS:
        src = shutil.which(tool)
        assert src, f"{tool} not found on this machine — cannot build fallback PATH"
        (bin_dir / tool).symlink_to(src)
    return str(bin_dir)


def test_dispatches_to_python_when_available(run_hook, tmp_home):
    assert shutil.which("python3"), "python3 must be on PATH for this test"
    result = run_hook(
        SCRIPT,
        _payload(f"{tmp_home}/.claude/institution/rules/x.md"),
        env_overrides={"HOME": str(tmp_home), "TLOR_INSTITUTION_GUARD": "1"},
    )
    assert result.returncode == 0
    decision = result.decision
    assert decision is not None
    assert decision["hookSpecificOutput"]["permissionDecision"] == "deny"


@pytest.mark.skipif(not have_jq(), reason="jq not on PATH")
def test_falls_back_to_bash_when_python3_absent(run_hook, tmp_home, tmp_path):
    fallback_path = _no_python_path(tmp_path)
    result = run_hook(
        SCRIPT,
        _payload(f"{tmp_home}/.claude/institution/rules/x.md"),
        env_overrides={
            "HOME": str(tmp_home),
            "TLOR_INSTITUTION_GUARD": "1",
            "PATH": fallback_path,
        },
    )
    assert result.returncode == 0
    decision = result.decision
    assert decision is not None
    assert decision["hookSpecificOutput"]["permissionDecision"] == "deny"
