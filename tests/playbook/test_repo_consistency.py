# -*- coding: utf-8 -*-
"""Repo-wide gates on the real playbook content (not fixtures)."""
import subprocess
import sys

from conftest import REPO_ROOT

SCRIPTS_DIR = REPO_ROOT / "playbook" / "scripts"
ENTRIES_DIR = REPO_ROOT / "agent_doc" / "algorithms"
METADATA_DIR = REPO_ROOT / "playbook" / "metadata" / "algorithms"
TESTS_DIR = REPO_ROOT / "tests" / "playbook" / "algorithms"
SKIP = ("README.md", "INDEX.md")


def _run(*args):
    return subprocess.run([sys.executable] + [str(a) for a in args], cwd=str(REPO_ROOT),
                          stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                          universal_newlines=True)


def test_index_matches_build_index_output(tmp_path):
    out = tmp_path / "INDEX.md"
    proc = _run(SCRIPTS_DIR / "build_index.py", "--out", out)
    assert proc.returncode == 0, proc.stdout
    committed = (ENTRIES_DIR / "INDEX.md").read_bytes()
    assert out.read_bytes() == committed, \
        "agent_doc/algorithms/INDEX.md is stale; rerun: python3 playbook/scripts/build_index.py"


def test_validate_all_passes(tmp_path):
    proc = _run(SCRIPTS_DIR / "validate.py", "--all", "--impl-dir", tmp_path / "impl")
    assert proc.returncode == 0, proc.stdout


def test_entry_metadata_and_test_files_pair_up():
    entries = {p.stem for p in ENTRIES_DIR.glob("*.md") if p.name not in SKIP}
    metadata = {p.stem for p in METADATA_DIR.glob("*.yaml")}
    # test file names flatten the id's dots to underscores
    tests = {p.stem[len("test_"):] for p in TESTS_DIR.glob("test_*.py")}
    flat = {e.replace(".", "_") for e in entries}
    assert entries, "no entries found in %s" % ENTRIES_DIR
    assert entries == metadata, "entries vs metadata: %s" % sorted(entries ^ metadata)
    assert flat == tests, "entries vs tests: %s" % sorted(flat ^ tests)
