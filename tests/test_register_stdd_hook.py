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


def _run_remove(run_hook, settings_path, hook_script):
    return run_hook(SCRIPT, "", args=[str(settings_path), str(hook_script), "--remove"])


def test_remove_removes_unquoted_command_entry(run_hook, tmp_path):
    """A hand-edited/differently-quoted entry (unquoted command, not the
    exact `python3 "<path>"` string this installer writes) must still be
    recognized and removed — matching is by substring on
    'stdd_test_guard.py', not exact string equality."""
    settings_path = tmp_path / "settings.json"
    hook_script = tmp_path / "stdd_test_guard.py"
    settings_path.write_text(json.dumps({
        "hooks": {
            "PreToolUse": [
                {
                    "matcher": "Write|Edit|NotebookEdit",
                    "hooks": [{"type": "command", "command": "python3 %s" % hook_script}],
                }
            ]
        }
    }), encoding="utf-8")

    result = _run_remove(run_hook, settings_path, hook_script)
    assert result.returncode == 0
    assert "unregistered" in result.stdout

    settings = json.loads(settings_path.read_text(encoding="utf-8"))
    assert settings["hooks"]["PreToolUse"] == []


def test_remove_removes_duplicated_entry_both_copies(run_hook, tmp_path):
    """Two differently-quoted registrations of the same script (e.g. from a
    hand-edit plus a re-run) must BOTH be removed in one pass."""
    settings_path = tmp_path / "settings.json"
    hook_script = tmp_path / "stdd_test_guard.py"
    settings_path.write_text(json.dumps({
        "hooks": {
            "PreToolUse": [
                {
                    "matcher": "Write|Edit|NotebookEdit",
                    "hooks": [{"type": "command", "command": 'python3 "%s"' % hook_script}],
                },
                {
                    "matcher": "Write|Edit|NotebookEdit",
                    "hooks": [{"type": "command", "command": "python3.12 %s" % hook_script}],
                },
            ]
        }
    }), encoding="utf-8")

    result = _run_remove(run_hook, settings_path, hook_script)
    assert result.returncode == 0

    settings = json.loads(settings_path.read_text(encoding="utf-8"))
    assert settings["hooks"]["PreToolUse"] == []


def test_remove_preserves_unrelated_matcher_block(run_hook, tmp_path):
    """An unrelated PreToolUse matcher block (a different hook entirely)
    must survive untouched by --remove."""
    settings_path = tmp_path / "settings.json"
    hook_script = tmp_path / "stdd_test_guard.py"
    settings_path.write_text(json.dumps({
        "hooks": {
            "PreToolUse": [
                {
                    "matcher": "Bash",
                    "hooks": [{"type": "command", "command": "python3 /some/other_hook.py"}],
                },
                {
                    "matcher": "Write|Edit|NotebookEdit",
                    "hooks": [{"type": "command", "command": 'python3 "%s"' % hook_script}],
                },
            ]
        }
    }), encoding="utf-8")

    result = _run_remove(run_hook, settings_path, hook_script)
    assert result.returncode == 0

    settings = json.loads(settings_path.read_text(encoding="utf-8"))
    entries = settings["hooks"]["PreToolUse"]
    assert len(entries) == 1
    assert entries[0]["matcher"] == "Bash"
    assert entries[0]["hooks"][0]["command"] == "python3 /some/other_hook.py"


def test_remove_malformed_container_shape_exits_with_clear_message(run_hook, tmp_path):
    """`hooks` being a list (not an object) must produce a clear error
    message and non-zero exit — not an AttributeError traceback."""
    settings_path = tmp_path / "settings.json"
    hook_script = tmp_path / "stdd_test_guard.py"
    settings_path.write_text(json.dumps({"hooks": ["not-an-object"]}), encoding="utf-8")

    result = _run_remove(run_hook, settings_path, hook_script)
    assert result.returncode != 0
    assert "Traceback" not in result.stderr
    assert "hooks" in result.stderr.lower()


def test_remove_backs_up_settings_before_rewrite(run_hook, tmp_path):
    settings_path = tmp_path / "settings.json"
    hook_script = tmp_path / "stdd_test_guard.py"
    _run_register(run_hook, settings_path, hook_script)
    original = settings_path.read_text(encoding="utf-8")

    result = _run_remove(run_hook, settings_path, hook_script)
    assert result.returncode == 0

    backups = list(tmp_path.glob("settings.json.bak-*"))
    assert len(backups) == 1
    assert backups[0].read_text(encoding="utf-8") == original


def test_remove_writes_through_symlink_without_severing_it(run_hook, tmp_path):
    """settings.json is commonly a symlink into a dotfiles repo. --remove
    must write through the symlink to the real target and leave the link
    itself intact — not replace the link with a plain file (R1)."""
    real_dir = tmp_path / "dotfiles"
    real_dir.mkdir()
    real_settings = real_dir / "real_settings.json"
    hook_script = tmp_path / "stdd_test_guard.py"
    real_settings.write_text(json.dumps({
        "hooks": {
            "PreToolUse": [
                {
                    "matcher": "Write|Edit|NotebookEdit",
                    "hooks": [{"type": "command", "command": 'python3 "%s"' % hook_script}],
                }
            ]
        }
    }), encoding="utf-8")

    link_path = tmp_path / "settings.json"
    link_path.symlink_to(real_settings)

    result = _run_remove(run_hook, link_path, hook_script)
    assert result.returncode == 0

    assert link_path.is_symlink(), "the symlink must survive --remove"
    assert link_path.resolve() == real_settings.resolve(), "the symlink must still point at the real dotfiles file"

    real_settings_after = json.loads(real_settings.read_text(encoding="utf-8"))
    assert real_settings_after["hooks"]["PreToolUse"] == [], "the real target must no longer contain the entry"


def test_remove_removes_entry_under_posttooluse(run_hook, tmp_path):
    """The scan must cover every hook event array under `hooks`, not just
    PreToolUse — an entry mentioning the script under PostToolUse (or any
    other event) must still be found and removed (R2)."""
    settings_path = tmp_path / "settings.json"
    hook_script = tmp_path / "stdd_test_guard.py"
    settings_path.write_text(json.dumps({
        "hooks": {
            "PostToolUse": [
                {
                    "matcher": "Write|Edit|NotebookEdit",
                    "hooks": [{"type": "command", "command": 'python3 "%s"' % hook_script}],
                }
            ]
        }
    }), encoding="utf-8")

    result = _run_remove(run_hook, settings_path, hook_script)
    assert result.returncode == 0
    assert "unregistered" in result.stdout

    settings = json.loads(settings_path.read_text(encoding="utf-8"))
    assert settings["hooks"]["PostToolUse"] == []


def test_remove_root_not_object_exits_with_clear_message(run_hook, tmp_path):
    """A settings.json whose JSON root is not an object (e.g. a bare list)
    must get the same clear ERROR + non-zero exit as the other malformed
    shapes, not an AttributeError traceback (R3)."""
    settings_path = tmp_path / "settings.json"
    hook_script = tmp_path / "stdd_test_guard.py"
    settings_path.write_text(json.dumps([]), encoding="utf-8")

    result = _run_remove(run_hook, settings_path, hook_script)
    assert result.returncode != 0
    assert "Traceback" not in result.stderr
    assert "ERROR" in result.stderr


def test_register_root_not_object_exits_with_clear_message(run_hook, tmp_path):
    """Same root-type guard for the register path — a JSON root that is a
    string, not an object, must not crash with an AttributeError (R3)."""
    settings_path = tmp_path / "settings.json"
    hook_script = tmp_path / "stdd_test_guard.py"
    settings_path.write_text(json.dumps("x"), encoding="utf-8")

    result = _run_register(run_hook, settings_path, hook_script)
    assert result.returncode != 0
    assert "Traceback" not in result.stderr
    assert "ERROR" in result.stderr
