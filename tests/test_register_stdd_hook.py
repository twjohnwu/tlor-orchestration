# -*- coding: utf-8 -*-
"""Black-box tests for hooks/register_stdd_hook.py (invoked as a CLI script,
not imported — it has no importable API of its own)."""
import json

from conftest import HOOKS_DIR

SCRIPT = HOOKS_DIR / "register_stdd_hook.py"


def _run_register(run_hook, settings_path, hook_script):
    return run_hook(SCRIPT, "", args=[str(settings_path), str(hook_script)])


def test_first_run_registers_pretooluse_entry(run_hook, tmp_path):
    settings_path = tmp_path / "settings.json"
    hook_script = tmp_path / "stdd_test_guard.py"
    result = _run_register(run_hook, settings_path, hook_script)
    assert result.returncode == 0
    assert "registered" in result.stdout

    settings = json.loads(settings_path.read_text(encoding="utf-8"))
    entries = settings["hooks"]["PreToolUse"]
    assert len(entries) == 1
    assert entries[0]["matcher"] == "Write|Edit|NotebookEdit"
    assert entries[0]["hooks"][0]["command"] == 'python3 "%s"' % hook_script

    assert not (tmp_path / "settings.json.tmp").exists()


def test_second_run_is_idempotent(run_hook, tmp_path):
    settings_path = tmp_path / "settings.json"
    hook_script = tmp_path / "stdd_test_guard.py"
    _run_register(run_hook, settings_path, hook_script)
    result = _run_register(run_hook, settings_path, hook_script)

    assert result.returncode == 0
    assert "already registered" in result.stdout

    settings = json.loads(settings_path.read_text(encoding="utf-8"))
    entries = settings["hooks"]["PreToolUse"]
    assert len(entries) == 1  # no duplicate entry
    assert not (tmp_path / "settings.json.tmp").exists()
