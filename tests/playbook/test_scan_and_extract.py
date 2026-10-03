# -*- coding: utf-8 -*-
"""Tests for playbook/scripts/{scan_sources,extract_candidates}.py.

Fixture trees under tmp_path only — the real source clones are never read.
"""
import importlib
import json
import subprocess
import sys

from conftest import REPO_ROOT

SCRIPTS_DIR = REPO_ROOT / "playbook" / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

scan_sources = importlib.import_module("scan_sources")
extract_candidates = importlib.import_module("extract_candidates")

SOURCES_YAML = """\
primary:
  - repo: a/prim
    local_dir: prim
    commit: c1
    license: MIT
secondary:
  - repo: b/sec
    local_dir: sec
    commit: c2
    license: MIT
"""
TAXONOMY_YAML = """\
algorithms:
  - {id: search.binary_search, name: Binary Search, aliases: [binary_search, bisect_left]}
  - {id: graph.nothing, name: Nothing, aliases: [zzz_nothing]}
"""


def _write(path, text="x = 1\n"):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _build(tmp_path):
    root = tmp_path / "root"
    _write(root / "Primary" / "prim" / "searches" / "binary_search.py",
           '"""Binary search docs."""\n\ndef f():\n    pass\n')
    _write(root / "Primary" / "prim" / "other" / "uses_binary_search_here.py")
    _write(root / "Primary" / "prim" / "other" / "Binary-Search_2.py")
    _write(root / "Primary" / "prim" / "README.md",
           "# Intro\nhello\n## Binary Search\nHalve the range.\n")
    _write(root / "Secondary" / "sec" / "BinarySearch.cpp", "// bs\nint a;\n")
    _write(root / "Primary" / "prim" / ".git" / "config", "ignored")
    (tmp_path / "sources.yaml").write_text(SOURCES_YAML, encoding="utf-8")
    (tmp_path / "taxonomy.yaml").write_text(TAXONOMY_YAML, encoding="utf-8")
    return root


def _inventory(tmp_path, root):
    out = tmp_path / "inv.jsonl"
    rc = scan_sources.main(["--sources-root", str(root), "--sources",
                            str(tmp_path / "sources.yaml"), "--out", str(out)])
    assert rc == 0
    return out


def _extract(tmp_path, root, inv, ids):
    out_dir = tmp_path / "evidence"
    rc = extract_candidates.main([
        "--sources-root", str(root), "--sources", str(tmp_path / "sources.yaml"),
        "--inventory", str(inv), "--taxonomy", str(tmp_path / "taxonomy.yaml"),
        "--out-dir", str(out_dir)] + sum([["--id", i] for i in ids], []))
    assert rc == 0
    return out_dir


def test_normalization():
    assert scan_sources.normalize("Binary-Search Tree") == "binary_search_tree"
    assert scan_sources.normalize("DijkstraHeap") == "dijkstra_heap"
    assert scan_sources.candidate_name("Binary-Search_2.py") == "binary_search"
    assert scan_sources.candidate_name("test_foo.py") == "foo"
    assert scan_sources.candidate_name("FooTest.java") == "foo"
    assert scan_sources.candidate_name("BFS.cpp") == "bfs"


def test_inventory_skips_vcs_and_large_files(tmp_path):
    root = _build(tmp_path)
    _write(root / "Primary" / "prim" / "big.py", "#" * (200 * 1024 + 1))
    rows = [json.loads(l) for l in _inventory(tmp_path, root).read_text().splitlines()]
    paths = [r["path"] for r in rows if r["source"] == "a/prim"]
    assert not any(p.startswith(".git/") for p in paths)
    assert "big.py" not in paths
    assert paths == sorted(paths)
    row = [r for r in rows if r["path"] == "searches/binary_search.py"][0]
    assert row["license"] == "MIT" and row["commit"] == "c1"
    assert row["category_guess"] == "searches" and row["language"] == "python"


def test_exact_match_precedes_substring(tmp_path):
    root = _build(tmp_path)
    inv = _inventory(tmp_path, root)
    out_dir = _extract(tmp_path, root, inv, ["search.binary_search"])
    data = json.loads((out_dir / "search.binary_search.json").read_text())
    prim = [s["path"] for s in data["sources"] if s["tier"] == "primary"]
    assert prim[0] in ("searches/binary_search.py", "other/Binary-Search_2.py")
    assert prim[-1] == "other/uses_binary_search_here.py"
    sec = [s for s in data["sources"] if s["tier"] == "secondary"]
    assert sec == [] or sec[0]["path"] == "BinarySearch.cpp"
    first = [s for s in data["sources"] if s["path"] == "searches/binary_search.py"][0]
    assert first["comments_or_docstring"] == "Binary search docs."
    assert first["readme_excerpt"].startswith("## Binary Search")
    assert "unmatched_hint" not in data


def test_per_repo_cap_and_size_truncation(tmp_path):
    root = _build(tmp_path)
    for i in range(6):
        _write(root / "Primary" / "prim" / "d" / ("binary_search_v%d.py" % i))
    _write(root / "Primary" / "prim" / "searches" / "binary_search.py",
           "y = 1\n" * 10000)
    inv = _inventory(tmp_path, root)
    out_dir = _extract(tmp_path, root, inv, ["search.binary_search"])
    data = json.loads((out_dir / "search.binary_search.json").read_text())
    prim = [s for s in data["sources"] if s["tier"] == "primary"]
    assert len(prim) == extract_candidates.MAX_FILES_PER_REPO
    big = [s for s in prim if s["path"] == "searches/binary_search.py"][0]
    assert big["code_truncated"] is True
    assert len(big["code"]) <= extract_candidates.CODE_CAP
    small = [s for s in prim if s["path"] != "searches/binary_search.py"][0]
    assert small["code_truncated"] is False


def test_unmatched_hint_when_no_primary(tmp_path):
    root = _build(tmp_path)
    inv = _inventory(tmp_path, root)
    out_dir = _extract(tmp_path, root, inv, ["graph.nothing"])
    data = json.loads((out_dir / "graph.nothing.json").read_text())
    assert data["sources"] == []
    assert "zzz_nothing" in data["unmatched_hint"]


def _git_clone(tmp_path):
    root = tmp_path / "clone"
    root.mkdir()
    (root / "a.py").write_text("x = 1\n")
    env_cfg = ["-c", "user.name=t", "-c", "user.email=t@example.com"]
    subprocess.check_call(["git", "init", "-q", str(root)])
    subprocess.check_call(["git", "-C", str(root), "add", "a.py"])
    subprocess.check_call(["git", "-C", str(root)] + env_cfg + ["commit", "-q", "-m", "x"])
    head = subprocess.check_output(["git", "-C", str(root), "rev-parse", "HEAD"],
                                   universal_newlines=True).strip()
    return root, head


def test_commit_warning_on_head_mismatch(tmp_path):
    root, head = _git_clone(tmp_path)
    assert scan_sources.commit_warning(root, {"repo": "o/r", "commit": head}) is None
    warning = scan_sources.commit_warning(root, {"repo": "o/r", "commit": "0" * 40})
    assert warning.startswith("WARNING:") and head in warning


def test_commit_warning_skipped_without_git(tmp_path):
    assert scan_sources.commit_warning(tmp_path, {"repo": "o/r", "commit": "0" * 40}) is None
