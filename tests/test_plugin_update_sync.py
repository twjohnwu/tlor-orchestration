# -*- coding: utf-8 -*-
"""Black-box tests for hooks/plugin_update_sync.py.

SessionStart hook: when a `.tlor-init-state` marker under ~/.claude or
$CLAUDE_PROJECT_DIR/.claude records a version different from
${CLAUDE_PLUGIN_ROOT}'s plugin.json, run scripts/tlor_sync.py, bump the
marker, and emit systemMessage + additionalContext. Silent otherwise; never
blocks (always exit 0). HOME is pointed at a tmp dir in every test.
"""
import json
import os
import shutil
import time

from conftest import HOOKS_DIR, REPO_ROOT

SCRIPT = HOOKS_DIR / "plugin_update_sync.py"
OLD = "0.0.1"


def _plugin_version():
    path = REPO_ROOT / ".claude-plugin" / "plugin.json"
    return json.loads(path.read_text(encoding="utf-8"))["version"]


def _write_marker(claude_dir, version, level="user"):
    claude_dir.mkdir(parents=True, exist_ok=True)
    marker = claude_dir / ".tlor-init-state"
    marker.write_text(json.dumps({"version": version, "level": level,
                                  "synced_at": "2026-01-01T00:00:00Z"}),
                      encoding="utf-8")
    return marker


def _marker_version(marker):
    return json.loads(marker.read_text(encoding="utf-8"))["version"]


def _run(run_hook, home, project, plugin_root=REPO_ROOT):
    return run_hook(SCRIPT, {"hook_event_name": "SessionStart", "source": "startup"},
                    env_overrides={"HOME": str(home),
                                   "CLAUDE_PROJECT_DIR": str(project),
                                   "CLAUDE_PLUGIN_ROOT": str(plugin_root)})


def _dirs(tmp_path):
    home = tmp_path / "home"
    project = tmp_path / "project"
    home.mkdir()
    project.mkdir()
    return home, project


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


def test_version_change_syncs_bumps_marker_and_reports(run_hook, tmp_path):
    home, project = _dirs(tmp_path)
    claude = home / ".claude"
    marker = _write_marker(claude, OLD)
    (claude / "agents").mkdir()
    (claude / "agents" / "dwarf-smith.md").write_text("custom\n", encoding="utf-8")

    result = _run(run_hook, home, project)

    assert result.returncode == 0
    decision = result.decision
    new = _plugin_version()
    expected = ("tlor %s→%s synced: 15 agents (1 backed up), 6 rules, agent_doc, "
                "workflows. Run /tlor-init for optional rules / STDD / hooks / routing."
                % (OLD, new))
    assert decision["systemMessage"] == expected
    assert decision["hookSpecificOutput"]["hookEventName"] == "SessionStart"
    assert decision["hookSpecificOutput"]["additionalContext"] == expected

    state = json.loads(marker.read_text(encoding="utf-8"))
    assert state["version"] == new and state["level"] == "user"
    assert state["synced_at"] != "2026-01-01T00:00:00Z"
    assert len(list((claude / "agents").glob("*.md"))) == 15
    assert len(list((claude / "agents").glob("dwarf-smith.md.bak-*"))) == 1
    assert (claude / "workflows" / "stdd-execute.js").is_file()
    assert not (claude / ".tlor-sync.lock").exists()


def test_project_level_marker_is_synced_too(run_hook, tmp_path):
    home, project = _dirs(tmp_path)
    marker = _write_marker(project / ".claude", OLD, level="project")
    result = _run(run_hook, home, project)
    assert result.returncode == 0
    assert "synced: 15 agents (0 backed up)" in result.decision["systemMessage"]
    state = json.loads(marker.read_text(encoding="utf-8"))
    assert state["version"] == _plugin_version() and state["level"] == "project"
    assert (project / ".claude" / "rules" / "dispatch.md").is_file()
    assert not (home / ".claude").exists()


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
    plugin = tmp_path / "plugin"
    (plugin / ".claude-plugin").mkdir(parents=True)
    (plugin / "scripts").mkdir()
    shutil.copy(str(REPO_ROOT / ".claude-plugin" / "plugin.json"),
                str(plugin / ".claude-plugin" / "plugin.json"))
    shutil.copy(str(REPO_ROOT / "scripts" / "tlor_sync.py"),
                str(plugin / "scripts" / "tlor_sync.py"))
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
    assert "synced" in result.decision["systemMessage"]
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
