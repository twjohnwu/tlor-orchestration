# -*- coding: utf-8 -*-
"""Tests for scripts/tlor_sync.py — the non-interactive /tlor-init sync
(Step 3 agents, Step 4 rules + agent_doc, Step 11 workflows + scripts).

Runs the script as a subprocess against the real checked-in plugin tree,
with a tmp dir as the install target. Never touches the real ~/.claude.
"""
import ast
import json
import os
import re
import subprocess
import sys

from conftest import REPO_ROOT

SCRIPT = REPO_ROOT / "scripts" / "tlor_sync.py"
HOOK = REPO_ROOT / "hooks" / "plugin_update_sync.py"

# Same awk program as install.sh's inject_version, so the Python port can be
# checked byte-for-byte against the shell original.
INJECT_VERSION_AWK = r'''
    NR==1 && $0=="---" { print; infm=1; next }
    infm && /^version:/ { print "version: " ver; done=1; next }
    infm && $0=="---" { if (!done) print "version: " ver; print; infm=0; next }
    { print }
'''


def _plugin_version():
    path = REPO_ROOT / ".claude-plugin" / "plugin.json"
    return json.loads(path.read_text(encoding="utf-8"))["version"]


def _run(*args):
    proc = subprocess.run(
        [sys.executable, str(SCRIPT)] + [str(a) for a in args],
        capture_output=True, text=True,
    )
    return proc


def _sync(target, *extra):
    proc = _run("--plugin-root", REPO_ROOT, "--target", target, *extra)
    assert proc.returncode == 0, proc.stderr
    return json.loads(proc.stdout)


def _md_names(path):
    return sorted(p.name for p in path.glob("*.md"))


def test_fresh_target_gets_agents_rules_agent_doc_workflows_and_scripts(tmp_path):
    target = tmp_path / "claude"
    target.mkdir()
    summary = _sync(target)

    agent_names = _md_names(REPO_ROOT / "agents")
    assert len(agent_names) == 15
    assert _md_names(target / "agents") == agent_names
    assert summary["agents"] == {"installed": 15, "updated": 0, "unchanged": 0}

    rule_names = _md_names(REPO_ROOT / "rules")
    assert len(rule_names) == 6
    assert _md_names(target / "rules") == rule_names
    version_line = "version: " + _plugin_version()
    for name in rule_names:
        assert version_line in (target / "rules" / name).read_text(encoding="utf-8").splitlines()

    assert (target / "agent_doc" / "builder-codex.md").is_file()
    assert (target / "agent_doc" / "zh_tw" / "patterns.md").is_file()
    assert not (target / "agent_doc" / "customize").exists()

    assert (target / "workflows" / "stdd-execute.js").is_file()
    assert (target / "workflows" / ".tlor-manifest").read_text().split() == ["stdd-execute.js"]
    assert (target / "scripts" / ".tlor-manifest").read_text().split() == [
        "stdd_custody_check.py", "stdd_verify.py"]
    assert not (target / "scripts" / "check_links.py").exists()
    assert not (target / "scripts" / "tlor_sync.py").exists()
    assert summary["backups"] == 0


def test_rules_version_injection_matches_install_sh_awk(tmp_path):
    target = tmp_path / "claude"
    target.mkdir()
    _sync(target)
    for src in sorted((REPO_ROOT / "rules").glob("*.md")):
        expected = subprocess.run(
            ["awk", "-v", "ver=" + _plugin_version(), INJECT_VERSION_AWK, str(src)],
            capture_output=True, text=True, check=True,
        ).stdout
        assert (target / "rules" / src.name).read_text(encoding="utf-8") == expected, src.name


def test_customized_agent_is_backed_up_then_overwritten(tmp_path):
    target = tmp_path / "claude"
    (target / "agents").mkdir(parents=True)
    live = target / "agents" / "gondor-builder.md"
    live.write_text("my customized role\n", encoding="utf-8")

    summary = _sync(target)

    assert live.read_bytes() == (REPO_ROOT / "agents" / "gondor-builder.md").read_bytes()
    backups = list((target / "agents").glob("gondor-builder.md.bak-*"))
    assert len(backups) == 1
    assert backups[0].read_text(encoding="utf-8") == "my customized role\n"
    assert summary["backups"] == 1
    assert summary["backup_paths"] == [str(backups[0])]
    assert summary["agents"] == {"installed": 14, "updated": 1, "unchanged": 0}


def test_second_run_reports_everything_unchanged_and_makes_no_backup(tmp_path):
    target = tmp_path / "claude"
    target.mkdir()
    _sync(target)
    summary = _sync(target)
    for asset in ("agents", "rules", "agent_doc", "workflows", "scripts"):
        assert summary[asset]["installed"] == 0, asset
        assert summary[asset]["updated"] == 0, asset
    assert summary["backups"] == 0
    assert not list((target / "agents").glob("*.bak-*"))


def test_customize_dirs_and_routing_files_are_untouched(tmp_path):
    target = tmp_path / "claude"
    (target / "rules" / "customize").mkdir(parents=True)
    (target / "agent_doc" / "customize").mkdir(parents=True)
    user_rule = target / "rules" / "customize" / "lessons.md"
    user_doc = target / "agent_doc" / "customize" / "README.md"
    claude_md = target / "CLAUDE.md"
    user_rule.write_text("mine\n", encoding="utf-8")
    user_doc.write_text("mine too\n", encoding="utf-8")
    claude_md.write_text("@AGENTS.md\n", encoding="utf-8")

    _sync(target)

    assert user_rule.read_text(encoding="utf-8") == "mine\n"
    assert user_doc.read_text(encoding="utf-8") == "mine too\n"
    assert claude_md.read_text(encoding="utf-8") == "@AGENTS.md\n"
    assert not (target / "AGENTS.md").exists()
    assert not (target / "hooks").exists()
    assert not (target / "skills").exists()


def test_existing_install_sh_manifest_is_refreshed_but_none_created(tmp_path):
    target = tmp_path / "claude"
    (target / "agent_doc").mkdir(parents=True)
    (target / "agent_doc" / ".tlor-manifest").write_text("stale.md\n", encoding="utf-8")

    _sync(target)

    lines = (target / "agent_doc" / ".tlor-manifest").read_text(encoding="utf-8").split()
    assert "zh_tw/patterns.md" in lines and "stale.md" not in lines
    assert not any(l.startswith("customize/") for l in lines)
    assert not (target / "agents" / ".tlor-manifest").exists()
    assert not (target / "rules" / ".tlor-manifest").exists()


def test_dry_run_writes_nothing(tmp_path):
    target = tmp_path / "claude"
    target.mkdir()
    summary = _sync(target, "--dry-run")
    assert summary["dry_run"] is True
    assert summary["agents"]["installed"] == 15
    assert os.listdir(str(target)) == []


def test_write_state_records_version_level_and_timestamp(tmp_path):
    target = tmp_path / "claude"
    target.mkdir()
    proc = _run("--plugin-root", REPO_ROOT, "--target", target,
                "--write-state", "--level", "project")
    assert proc.returncode == 0, proc.stderr
    state = json.loads((target / ".tlor-init-state").read_text(encoding="utf-8"))
    assert state["version"] == _plugin_version()
    assert state["level"] == "project"
    assert state["synced_at"].endswith("Z")
    assert list(target.iterdir()) == [target / ".tlor-init-state"]


def test_write_state_requires_level(tmp_path):
    proc = _run("--target", tmp_path, "--write-state")
    assert proc.returncode != 0
    assert not (tmp_path / ".tlor-init-state").exists()


def test_unreadable_plugin_root_exits_nonzero(tmp_path):
    target = tmp_path / "claude"
    target.mkdir()
    proc = _run("--plugin-root", tmp_path / "no-such-plugin", "--target", target)
    assert proc.returncode == 1
    assert "tlor_sync: error:" in proc.stderr
    assert os.listdir(str(target)) == []


def test_new_scripts_parse_as_python_3_7():
    for path in (SCRIPT, HOOK):
        source = path.read_text(encoding="utf-8")
        if sys.version_info >= (3, 8):
            ast.parse(source, filename=str(path), feature_version=(3, 7))
        else:
            # Running on 3.7 itself is the stricter check; feature_version
            # only exists from 3.8 on.
            ast.parse(source, filename=str(path))


def test_runtime_scripts_match_install_sh_scripts():
    # Both routes must write the same scripts manifest; tlor_sync.py itself
    # is run from the plugin root and is never installed.
    text = (REPO_ROOT / "install.sh").read_text(encoding="utf-8")
    match = re.search(r'^SCRIPTS="([^"]*)"', text, re.MULTILINE)
    assert match, "install.sh: no SCRIPTS= line"
    source = SCRIPT.read_text(encoding="utf-8")
    tree = ast.parse(source)
    runtime = None
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
                getattr(t, "id", None) == "RUNTIME_SCRIPTS" for t in node.targets):
            runtime = tuple(ast.literal_eval(node.value))
    assert runtime == tuple(match.group(1).split())
    assert "tlor_sync.py" not in runtime
