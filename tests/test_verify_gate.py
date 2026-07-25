# -*- coding: utf-8 -*-
"""Black-box tests for hooks/verify_gate.py (Stop hook)."""
import json

from conftest import HOOKS_DIR

SCRIPT = HOOKS_DIR / "verify_gate.py"


def _user_entry(text):
    return {"type": "user", "message": {"content": text}}


def _assistant_tool_use(name, tool_input):
    return {
        "type": "assistant",
        "message": {"content": [{"type": "tool_use", "name": name, "input": tool_input}]},
    }


def _write_transcript(tmp_path, entries):
    path = tmp_path / "transcript.jsonl"
    with open(path, "w", encoding="utf-8") as fh:
        for entry in entries:
            fh.write(json.dumps(entry) + "\n")
    return path


def test_code_edited_without_test_command_blocks(run_hook, tmp_path):
    entries = [
        _user_entry("please fix the bug"),
        _assistant_tool_use("Edit", {"file_path": "foo.py"}),
    ]
    transcript = _write_transcript(tmp_path, entries)
    stdin = {"transcript_path": str(transcript), "stop_hook_active": False}
    result = run_hook(SCRIPT, stdin, env_overrides={"TLOR_VERIFY_GATE": "1"})
    assert result.returncode == 0
    decision = result.decision
    assert decision is not None
    assert decision["decision"] == "block"
    assert "foo.py" in decision["reason"]


def test_code_edited_with_test_command_does_not_block(run_hook, tmp_path):
    entries = [
        _user_entry("please fix the bug"),
        _assistant_tool_use("Edit", {"file_path": "foo.py"}),
        _assistant_tool_use("Bash", {"command": "pytest tests/ -q"}),
    ]
    transcript = _write_transcript(tmp_path, entries)
    stdin = {"transcript_path": str(transcript), "stop_hook_active": False}
    result = run_hook(SCRIPT, stdin, env_overrides={"TLOR_VERIFY_GATE": "1"})
    assert result.returncode == 0
    assert result.decision is None


def test_env_gate_unset_allows(run_hook, tmp_path):
    entries = [
        _user_entry("please fix the bug"),
        _assistant_tool_use("Edit", {"file_path": "foo.py"}),
    ]
    transcript = _write_transcript(tmp_path, entries)
    stdin = {"transcript_path": str(transcript), "stop_hook_active": False}
    result = run_hook(SCRIPT, stdin, env_overrides={"TLOR_VERIFY_GATE": ""})
    assert result.returncode == 0
    assert result.decision is None


def test_stop_hook_active_allows(run_hook, tmp_path):
    entries = [
        _user_entry("please fix the bug"),
        _assistant_tool_use("Edit", {"file_path": "foo.py"}),
    ]
    transcript = _write_transcript(tmp_path, entries)
    stdin = {"transcript_path": str(transcript), "stop_hook_active": True}
    result = run_hook(SCRIPT, stdin, env_overrides={"TLOR_VERIFY_GATE": "1"})
    assert result.returncode == 0
    assert result.decision is None


def test_missing_transcript_fails_open(run_hook, tmp_path):
    stdin = {"transcript_path": str(tmp_path / "does-not-exist.jsonl"), "stop_hook_active": False}
    result = run_hook(SCRIPT, stdin, env_overrides={"TLOR_VERIFY_GATE": "1"})
    assert result.returncode == 0
    assert result.decision is None


def test_denied_edit_still_counts_as_code_edited_accepted_no_op(run_hook, tmp_path):
    """Documents current accepted behavior (user decision D6, no-op — see
    lessons.md 2026-07-25): analyze() counts every Edit/Write tool_use
    regardless of whether the tool_result that followed was itself denied
    (e.g. by institution_guard.py). This is a known, intentionally-not-fixed
    limitation, not a bug to chase — it can produce one false-positive block
    per turn but never fails open incorrectly."""
    entries = [
        _user_entry("please edit the rules file"),
        _assistant_tool_use("Edit", {"file_path": "foo.py"}),
        {
            "type": "tool_result",
            "message": {
                "content": json.dumps({
                    "hookSpecificOutput": {"permissionDecision": "deny"}
                })
            },
        },
    ]
    transcript = _write_transcript(tmp_path, entries)
    stdin = {"transcript_path": str(transcript), "stop_hook_active": False}
    result = run_hook(SCRIPT, stdin, env_overrides={"TLOR_VERIFY_GATE": "1"})
    decision = result.decision
    assert decision is not None
    assert decision["decision"] == "block"
