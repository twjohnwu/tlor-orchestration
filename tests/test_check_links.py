# -*- coding: utf-8 -*-
"""Tests for scripts/check_links.py's rules/*.md dead-reference check.

check_links.py has no CLI override for its repo-root paths (they're derived
from `__file__`), so these tests import the module directly and monkeypatch
its `RULES_DIR`/`AGENT_DOC_DIR` globals to point at a synthetic tmp_path
tree — no real repo content is read.
"""
import importlib
import sys

from conftest import REPO_ROOT

SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

check_links = importlib.import_module("check_links")


def _make_tree(tmp_path):
    """Build a synthetic rules/ + agent_doc/ tree (with a language subdir)
    under tmp_path and return (rules_dir, agent_doc_dir)."""
    rules_dir = tmp_path / "rules"
    rules_dir.mkdir()
    agent_doc_dir = tmp_path / "agent_doc"
    agent_doc_dir.mkdir()
    (agent_doc_dir / "flat-doc.md").write_text("flat doc\n", encoding="utf-8")
    subdir = agent_doc_dir / "zh_tw"
    subdir.mkdir()
    (subdir / "patterns.md").write_text("patterns doc\n", encoding="utf-8")
    return rules_dir, agent_doc_dir


def test_two_level_qualified_agent_doc_ref_resolves(tmp_path, monkeypatch):
    """GIVEN a rules/*.md file references `agent_doc/zh_tw/patterns.md`
    (a two-level qualified ref into a language subdirectory)
    WHEN check_rules_refs() runs
    THEN it resolves cleanly (no dead-reference error) — same as the
    existing one-level `agent_doc/flat-doc.md` form."""
    rules_dir, agent_doc_dir = _make_tree(tmp_path)
    (rules_dir / "caller.md").write_text(
        "See agent_doc/zh_tw/patterns.md and agent_doc/flat-doc.md.\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(check_links, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(check_links, "RULES_DIR", rules_dir)
    monkeypatch.setattr(check_links, "AGENT_DOC_DIR", agent_doc_dir)

    errors = check_links.check_rules_refs()

    assert errors == [], f"expected no dead-reference errors, got: {errors}"


def test_two_level_qualified_agent_doc_ref_to_missing_file_is_flagged(
    tmp_path, monkeypatch
):
    """GIVEN a rules/*.md file references a subdir file that does not exist
    (`agent_doc/zh_tw/missing.md`)
    WHEN check_rules_refs() runs
    THEN it reports exactly one dead-reference error naming that file."""
    rules_dir, agent_doc_dir = _make_tree(tmp_path)
    (rules_dir / "caller.md").write_text(
        "See agent_doc/zh_tw/missing.md.\n", encoding="utf-8"
    )
    monkeypatch.setattr(check_links, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(check_links, "RULES_DIR", rules_dir)
    monkeypatch.setattr(check_links, "AGENT_DOC_DIR", agent_doc_dir)

    errors = check_links.check_rules_refs()

    assert len(errors) == 1, f"expected exactly one error, got: {errors}"
    assert "zh_tw" in errors[0] and "missing.md" in errors[0]


def test_one_level_qualified_agent_doc_ref_still_resolves(tmp_path, monkeypatch):
    """Existing one-level behavior (`agent_doc/flat-doc.md`) must keep
    working unchanged alongside the new two-level support."""
    rules_dir, agent_doc_dir = _make_tree(tmp_path)
    (rules_dir / "caller.md").write_text(
        "See agent_doc/flat-doc.md.\n", encoding="utf-8"
    )
    monkeypatch.setattr(check_links, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(check_links, "RULES_DIR", rules_dir)
    monkeypatch.setattr(check_links, "AGENT_DOC_DIR", agent_doc_dir)

    errors = check_links.check_rules_refs()

    assert errors == [], f"expected no dead-reference errors, got: {errors}"
