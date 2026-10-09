# -*- coding: utf-8 -*-
"""Black-box tests for hooks/plugin_update_sync.py.

SessionStart hook, plugin route only: when a `.tlor-init-state` marker under
~/.claude records a version OLDER than ${CLAUDE_PLUGIN_ROOT}'s plugin.json,
run scripts/tlor_sync.py, bump the marker, and emit systemMessage +
additionalContext listing every backup path. Project-level markers
($CLAUDE_PROJECT_DIR/.claude, or level "project") only get a reminder.
Silent when opted out (TLOR_AUTO_SYNC=0/false/off), off the plugin route,
or when the marker is equal or newer; never blocks (always exit 0). HOME is
pointed at a tmp dir in every test.
"""
import hashlib
import json
import os
import shutil
import time

from conftest import HOOKS_DIR, REPO_ROOT

SCRIPT = HOOKS_DIR / "plugin_update_sync.py"
OLD = "0.0.1"
TAIL = ("New files apply from the next session. Run /tlor-init for optional "
        "rules / STDD / hooks / routing. Opt out: set TLOR_AUTO_SYNC=0 in "
        "~/.claude/settings.json env.")


def _plugin_version():
    path = REPO_ROOT / ".claude-plugin" / "plugin.json"
    return json.loads(path.read_text(encoding="utf-8"))["version"]


def _write_marker(claude_dir, version, level="user"):
    claude_dir.mkdir(parents=True, exist_ok=True)
    marker = claude_dir / ".tlor-init-state"
    state = {"level": level, "synced_at": "2026-01-01T00:00:00Z"}
    if version is not None:
        state["version"] = version
    marker.write_text(json.dumps(state), encoding="utf-8")
    return marker


def _marker_version(marker):
    return json.loads(marker.read_text(encoding="utf-8")).get("version")


def _tree(root):
    """relpath -> sha256 for every file under root (checksum snapshot)."""
    out = {}
    for dirpath, _dirs, files in os.walk(str(root)):
        for name in files:
            path = os.path.join(dirpath, name)
            with open(path, "rb") as fh:
                out[os.path.relpath(path, str(root))] = hashlib.sha256(fh.read()).hexdigest()
    return out


def _run(run_hook, home, project, plugin_root=REPO_ROOT, auto_sync=""):
    return run_hook(SCRIPT, {"hook_event_name": "SessionStart", "source": "startup"},
                    env_overrides={"HOME": str(home),
                                   "CLAUDE_PROJECT_DIR": str(project),
                                   "CLAUDE_PLUGIN_ROOT": str(plugin_root),
                                   "TLOR_AUTO_SYNC": auto_sync})


def _dirs(tmp_path):
    home = tmp_path / "home"
    project = tmp_path / "project"
    home.mkdir(parents=True)
    project.mkdir(parents=True)
    return home, project


def _fake_plugin(tmp_path, version):
    """A plugin root with only plugin.json (given version) and tlor_sync.py."""
    plugin = tmp_path / "plugin"
    (plugin / ".claude-plugin").mkdir(parents=True)
    (plugin / "scripts").mkdir()
    (plugin / ".claude-plugin" / "plugin.json").write_text(
        json.dumps({"name": "tlor", "version": version}), encoding="utf-8")
    shutil.copy(str(REPO_ROOT / "scripts" / "tlor_sync.py"),
                str(plugin / "scripts" / "tlor_sync.py"))
    return plugin


def test_no_marker_is_silent_and_writes_nothing(run_hook, tmp_path):
    home, project = _dirs(tmp_path)
    result = _run(run_hook, home, project)
    assert result.returncode == 0
    assert result.decision is None
    assert os.listdir(str(home)) == [] and os.listdir(str(project)) == []


def test_same_version_is_silent(run_hook, tmp_path):
    home, project = _dirs(tmp_path)
    marker = _write_marker(home / ".claude", _plugin_version())
    before = marker.read_text(encoding="utf-8")
    result = _run(run_hook, home, project)
    assert result.returncode == 0
    assert result.decision is None
    assert marker.read_text(encoding="utf-8") == before
    assert sorted(os.listdir(str(home / ".claude"))) == [".tlor-init-state"]


def test_downgrade_is_silent_and_writes_nothing(run_hook, tmp_path):
    home, project = _dirs(tmp_path)
    _write_marker(home / ".claude", "99.0.0")
    before = _tree(tmp_path)
    result = _run(run_hook, home, project)
    assert result.returncode == 0
    assert result.decision is None
    assert _tree(tmp_path) == before


def test_opt_out_values_are_silent_and_write_nothing(run_hook, tmp_path):
    home, project = _dirs(tmp_path)
    _write_marker(home / ".claude", OLD)
    before = _tree(tmp_path)
    for value in ("0", "false", "FALSE", "off", "Off"):
        result = _run(run_hook, home, project, auto_sync=value)
        assert result.returncode == 0
        assert result.stdout == "", value
        assert _tree(tmp_path) == before, value


def test_no_plugin_root_is_silent_and_writes_nothing(run_hook, tmp_path):
    home, project = _dirs(tmp_path)
    _write_marker(home / ".claude", OLD)
    before = _tree(tmp_path)
    result = _run(run_hook, home, project, plugin_root="")
    assert result.returncode == 0
    assert result.stdout == ""
    assert _tree(tmp_path) == before


def test_unparsable_plugin_version_is_silent(run_hook, tmp_path):
    home, project = _dirs(tmp_path)
    _write_marker(home / ".claude", OLD)
    plugin = _fake_plugin(tmp_path, "dev-build")
    before = _tree(home)
    result = _run(run_hook, home, project, plugin_root=plugin)
    assert result.returncode == 0
    assert result.stdout == ""
    assert _tree(home) == before


def test_upgrade_syncs_bumps_marker_and_lists_backups(run_hook, tmp_path):
    home, project = _dirs(tmp_path)
    claude = home / ".claude"
    marker = _write_marker(claude, OLD)
    (claude / "agents").mkdir()
    (claude / "agents" / "dwarf-smith.md").write_text("custom\n", encoding="utf-8")

    result = _run(run_hook, home, project)

    assert result.returncode == 0
    decision = result.decision
    new = _plugin_version()
    backups = list((claude / "agents").glob("dwarf-smith.md.bak-*"))
    assert len(backups) == 1
    msg = decision["systemMessage"]
    lines = msg.split("\n")
    assert lines[0] == ("tlor %s→%s synced to %s: 15 agents (1 backed up), 6 rules, "
                        "agent_doc, workflows." % (OLD, new, claude))
    assert "Backup: %s" % backups[0] in lines
    assert msg.endswith(TAIL)
    assert decision["hookSpecificOutput"]["hookEventName"] == "SessionStart"
    assert decision["hookSpecificOutput"]["additionalContext"] == msg

    state = json.loads(marker.read_text(encoding="utf-8"))
    assert state["version"] == new and state["level"] == "user"
    assert state["synced_at"] != "2026-01-01T00:00:00Z"
    assert len(list((claude / "agents").glob("*.md"))) == 15
    assert (claude / "workflows" / "stdd-execute.js").is_file()
    assert not (claude / "scripts" / "tlor_sync.py").exists()
    assert not (claude / ".tlor-sync.lock").exists()


def test_upgrade_without_backups_says_so(run_hook, tmp_path):
    home, project = _dirs(tmp_path)
    _write_marker(home / ".claude", OLD)
    result = _run(run_hook, home, project)
    lines = result.decision["systemMessage"].split("\n")
    assert "(0 backed up)" in lines[0]
    assert "no backups" in lines
    assert not any(line.startswith("Backup: ") for line in lines)


def test_missing_or_unparsable_marker_version_counts_as_older(run_hook, tmp_path):
    for name, version in (("missing", None), ("garbage", "not-a-version")):
        home, project = _dirs(tmp_path / name)
        marker = _write_marker(home / ".claude", version)
        result = _run(run_hook, home, project)
        assert result.returncode == 0
        assert " synced to " in result.decision["systemMessage"], name
        assert _marker_version(marker) == _plugin_version(), name


def test_project_dir_marker_gets_reminder_only(run_hook, tmp_path):
    home, project = _dirs(tmp_path)
    marker = _write_marker(project / ".claude", OLD, level="project")
    before = _tree(tmp_path)

    result = _run(run_hook, home, project)

    assert result.returncode == 0
    expected = ("tlor %s→%s: project-level install at %s not auto-synced; "
                "run /tlor-init there." % (OLD, _plugin_version(), project / ".claude"))
    assert result.decision["systemMessage"] == expected
    assert result.decision["hookSpecificOutput"]["additionalContext"] == expected
    assert _tree(tmp_path) == before
    assert _marker_version(marker) == OLD


def test_project_level_marker_under_home_gets_reminder_only(run_hook, tmp_path):
    home, project = _dirs(tmp_path)
    _write_marker(home / ".claude", OLD, level="project")
    before = _tree(tmp_path)
    result = _run(run_hook, home, project)
    assert "project-level install at %s not auto-synced" % (home / ".claude") \
        in result.decision["systemMessage"]
    assert _tree(tmp_path) == before


def test_invalid_marker_reports_failure_and_writes_nothing(run_hook, tmp_path):
    cases = (
        ("level", json.dumps({"version": OLD, "level": "global"})),
        ("array", json.dumps([OLD])),
        ("version-type", json.dumps({"version": 14, "level": "user"})),
        ("not-json", "{nope"),
    )
    for name, content in cases:
        home, project = _dirs(tmp_path / name)
        (home / ".claude").mkdir()
        (home / ".claude" / ".tlor-init-state").write_text(content, encoding="utf-8")
        before = _tree(tmp_path / name)
        result = _run(run_hook, home, project)
        assert result.returncode == 0
        msg = result.decision["systemMessage"]
        assert msg.startswith("tlor auto-sync failed: "), name
        assert msg.endswith("Run /tlor-init manually."), name
        assert _tree(tmp_path / name) == before, name


def test_unreadable_plugin_root_reports_failure_and_keeps_marker(run_hook, tmp_path):
    home, project = _dirs(tmp_path)
    marker = _write_marker(home / ".claude", OLD)
    result = _run(run_hook, home, project, plugin_root=tmp_path / "missing-plugin")
    assert result.returncode == 0
    msg = result.decision["systemMessage"]
    assert msg.startswith("tlor auto-sync failed: ")
    assert msg.endswith("Run /tlor-init manually.")
    assert _marker_version(marker) == OLD


def test_failure_mid_sync_releases_lock_and_keeps_marker(run_hook, tmp_path):
    # A plugin root whose version and sync script load fine, but whose
    # agents/ dir is missing, so tlor_sync raises after the lock is taken.
    home, project = _dirs(tmp_path)
    plugin = _fake_plugin(tmp_path, _plugin_version())
    marker = _write_marker(home / ".claude", OLD)

    result = _run(run_hook, home, project, plugin_root=plugin)

    assert result.returncode == 0
    assert "tlor auto-sync failed: missing source directory" in result.decision["systemMessage"]
    assert _marker_version(marker) == OLD
    assert not (home / ".claude" / ".tlor-sync.lock").exists()


def test_held_lock_skips_sync_silently(run_hook, tmp_path):
    home, project = _dirs(tmp_path)
    marker = _write_marker(home / ".claude", OLD)
    lock = home / ".claude" / ".tlor-sync.lock"
    lock.write_text("12345", encoding="utf-8")

    result = _run(run_hook, home, project)

    assert result.returncode == 0
    assert result.decision is None
    assert _marker_version(marker) == OLD
    assert lock.exists()
    assert not (home / ".claude" / "agents").exists()


def test_stale_lock_is_removed_and_sync_proceeds(run_hook, tmp_path):
    home, project = _dirs(tmp_path)
    marker = _write_marker(home / ".claude", OLD)
    lock = home / ".claude" / ".tlor-sync.lock"
    lock.write_text("12345", encoding="utf-8")
    old = time.time() - 20 * 60
    os.utime(str(lock), (old, old))

    result = _run(run_hook, home, project)

    assert result.returncode == 0
    assert " synced to " in result.decision["systemMessage"]
    assert _marker_version(marker) == _plugin_version()
    assert not lock.exists()


def test_hooks_json_registers_session_start_startup():
    data = json.loads((HOOKS_DIR / "hooks.json").read_text(encoding="utf-8"))
    entries = data["hooks"]["SessionStart"]
    assert any(
        e.get("matcher") == "startup"
        and any("plugin_update_sync.py" in h["command"] for h in e["hooks"])
        for e in entries
    )
    assert "Stop" in data["hooks"] and "PreToolUse" in data["hooks"]
