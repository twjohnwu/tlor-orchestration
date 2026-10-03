# -*- coding: utf-8 -*-
"""Tests for playbook/scripts/build_index.py and evaluate.py.

Both scripts take every path as a CLI/function argument, so the tests feed
them synthetic tmp_path trees; the real playbook/ content is never read.
"""
import importlib
import json
import math
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
SCRIPTS_DIR = REPO_ROOT / "playbook" / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

build_index = importlib.import_module("build_index")
evaluate = importlib.import_module("evaluate")

BFS_YAML = """\
id: graph.traversal.bfs
name: Breadth-First Search
signals:
  - unweighted graph
  - fewest steps
avoid_when:
  - weighted edges
confidence: high
review_required: true
"""

BS_YAML = """\
id: search.binary_search
name: Binary Search
signals:
  - sorted array
  - logarithmic time
avoid_when:
  - unsorted data
  - no monotonic condition
confidence: medium
"""


def _write_metadata(directory):
    directory.mkdir()
    (directory / "graph.traversal.bfs.yaml").write_text(BFS_YAML, encoding="utf-8")
    (directory / "search.binary_search.yaml").write_text(BS_YAML, encoding="utf-8")


def _run_build(metadata_dir, out):
    return subprocess.run(
        [sys.executable, str(SCRIPTS_DIR / "build_index.py"),
         "--metadata-dir", str(metadata_dir), "--out", str(out)],
        capture_output=True, text=True)


def test_build_index_exact_table(tmp_path):
    _write_metadata(tmp_path / "meta")
    out = tmp_path / "INDEX.md"
    proc = _run_build(tmp_path / "meta", out)
    assert proc.returncode == 0, proc.stderr
    lines = out.read_text(encoding="utf-8").splitlines()
    assert lines[-4:] == [
        "| id | name | signals | avoid_when | confidence |",
        "|---|---|---|---|---|",
        "| graph.traversal.bfs | Breadth-First Search | unweighted graph; fewest steps"
        " | weighted edges | high ⚠ review |",
        "| search.binary_search | Binary Search | sorted array; logarithmic time"
        " | unsorted data; no monotonic condition | medium |",
    ]
    assert "build_index.py" in lines[0] and "README.md" in "\n".join(lines)


def test_build_index_idempotent(tmp_path):
    _write_metadata(tmp_path / "meta")
    out = tmp_path / "INDEX.md"
    _run_build(tmp_path / "meta", out)
    first = out.read_bytes()
    _run_build(tmp_path / "meta", out)
    assert out.read_bytes() == first


def test_build_index_missing_field_names_file_and_field(tmp_path):
    meta = tmp_path / "meta"
    _write_metadata(meta)
    (meta / "search.binary_search.yaml").write_text(
        BS_YAML.replace("confidence: medium\n", ""), encoding="utf-8")
    proc = _run_build(meta, tmp_path / "INDEX.md")
    assert proc.returncode == 1
    assert "search.binary_search.yaml" in proc.stderr and "'confidence'" in proc.stderr
    assert not (tmp_path / "INDEX.md").exists()


def test_build_index_empty_dir_fails(tmp_path):
    (tmp_path / "meta").mkdir()
    proc = _run_build(tmp_path / "meta", tmp_path / "INDEX.md")
    assert proc.returncode == 1
    assert "no *.yaml metadata files" in proc.stderr


def test_build_index_id_must_match_filename(tmp_path):
    meta = tmp_path / "meta"
    meta.mkdir()
    (meta / "other.yaml").write_text(BS_YAML, encoding="utf-8")
    proc = _run_build(meta, tmp_path / "INDEX.md")
    assert proc.returncode == 1 and "must match the file name" in proc.stderr


def test_tokenize_and_singularize():
    assert evaluate.tokenize("The Shortest PATHS in a graph's edges!") == [
        "shortest", "path", "graph", "edge"]
    assert evaluate.singularize("queries") == "query"
    assert evaluate.singularize("class") == "class"
    assert evaluate.singularize("bfs") == "bfs"
    assert evaluate.tokenize("a of the") == []


def test_tokenize_keeps_negation_compounds():
    assert evaluate.tokenize("non-negative weights") == ["nonnegative", "weight"]
    assert evaluate.tokenize("non-empty list") == ["nonempty", "list"]
    assert evaluate.tokenize("k-th element") == ["th", "element"]
    assert "negative" not in evaluate.tokenize("non-negative")


def _row(*avoid_when):
    return evaluate.prepare({"id": "x.y", "name": "Xy", "signals": "alpha", "avoid_when": list(avoid_when)})


def test_rejects_one_token_phrase():
    assert evaluate.rejects("find a target in an unsorted array", _row("unsorted"))
    assert not evaluate.rejects("find a target in a sorted array", _row("unsorted"))


def test_rejects_three_token_phrase_needs_all_tokens():
    row = _row("negative edge weights")
    assert evaluate.rejects("graph with negative edge weights", row)
    assert not evaluate.rejects("graph with negative edge", row)


def test_rejects_five_token_phrase_matches_at_two():
    row = _row("blue green red yellow purple")
    assert evaluate.rejects("blue and red only", row)
    assert not evaluate.rejects("blue only", row)


def test_non_negative_does_not_collide_with_negative_phrase():
    assert not evaluate.rejects("route with non-negative edge weights", _row("negative edge weights"))


def _index(tmp_path):
    meta = tmp_path / "meta"
    _write_metadata(meta)
    out = tmp_path / "INDEX.md"
    assert _run_build(meta, out).returncode == 0
    return out


def _jsonl(path, items):
    path.write_text("".join(json.dumps(i) + "\n" for i in items), encoding="utf-8")


def test_evaluate_known_metrics_and_misses(tmp_path):
    index = _index(tmp_path)
    ev = tmp_path / "eval"
    ev.mkdir()
    _jsonl(ev / "retrieval.jsonl", [
        {"query": "fewest steps in an unweighted graph", "expected": "graph.traversal.bfs"},
        {"query": "search a sorted array", "expected": "search.binary_search"},
        # deliberate miss: no token overlap with any row
        {"query": "knapsack of items", "expected": "search.binary_search"},
    ])
    _jsonl(ev / "selection.jsonl", [
        {"query": "sorted array lookup", "candidates": ["graph.traversal.bfs", "search.binary_search"],
         "expected": "search.binary_search"},
        {"query": "sorted array lookup", "candidates": ["graph.traversal.bfs", "search.binary_search"],
         "expected": "graph.traversal.bfs"},
    ])
    _jsonl(ev / "rejection.jsonl", [
        {"query": "search unsorted data with no monotonic condition",
         "algorithm": "search.binary_search", "expected": "reject"},
        {"query": "search a sorted array", "algorithm": "search.binary_search", "expected": "reject"},
        {"query": "search a sorted array", "algorithm": "search.binary_search", "expected": "accept"},
    ])
    rows = [evaluate.prepare(r) for r in evaluate.parse_index(index)]
    res = evaluate.evaluate(rows, ev, 3)
    m = res["metrics"]
    assert m["recall@3"] == pytest.approx(2 / 3)
    assert m["mrr"] == pytest.approx(2 / 3)
    assert m["top1"] == pytest.approx(2 / 3)
    assert m["wrong_algorithm_rate"] == pytest.approx(0.5)
    assert m["constraint_violation_rate"] == pytest.approx(0.5)
    assert res["n"] == {"retrieval": 3, "selection": 2, "rejection": 3, "rejection_reject_cases": 2}
    assert res["misses"]["retrieval"] == [
        "knapsack of items -> got (none), expected search.binary_search"]
    assert len(res["misses"]["selection"]) == 1
    assert len(res["misses"]["rejection"]) == 1
    text = evaluate.render(res)
    assert "Constraint Violation Rate | 0.500 | 2" in text


def test_evaluate_cli_exits_zero_and_json(tmp_path):
    index = _index(tmp_path)
    ev = tmp_path / "eval"
    ev.mkdir()
    _jsonl(ev / "retrieval.jsonl", [{"query": "zzz", "expected": "search.binary_search"}])
    proc = subprocess.run(
        [sys.executable, str(SCRIPTS_DIR / "evaluate.py"), "--index", str(index),
         "--eval-dir", str(ev), "--json"], capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr
    data = json.loads(proc.stdout)
    assert data["metrics"]["top1"] == 0.0 and data["metrics"]["wrong_algorithm_rate"] is None


def test_heldout_reported_separately(tmp_path):
    index = _index(tmp_path)
    ev = tmp_path / "eval"
    ev.mkdir()
    _jsonl(ev / "retrieval.jsonl", [{"query": "search a sorted array", "expected": "search.binary_search"}])
    held = tmp_path / "blind.jsonl"
    _jsonl(held, [
        {"query": "search a sorted array", "expected": "search.binary_search"},
        {"query": "zzz", "expected": "search.binary_search"},
    ])
    rows = [evaluate.prepare(r) for r in evaluate.parse_index(index)]
    res = evaluate.evaluate(rows, ev, 3, held)
    assert res["n"]["retrieval"] == 1 and res["metrics"]["top1"] == 1.0
    assert res["heldout"]["n"] == 2
    assert res["heldout"]["metrics"]["top1"] == pytest.approx(0.5)
    assert res["heldout"]["misses"] == ["zzz -> got (none), expected search.binary_search"]
    assert res["misses"]["retrieval"] == []
    assert "Held-out (blind) retrieval" in evaluate.render(res)
    assert "heldout" not in evaluate.evaluate(rows, ev, 3)
    proc = subprocess.run(
        [sys.executable, str(SCRIPTS_DIR / "evaluate.py"), "--index", str(index),
         "--eval-dir", str(ev), "--heldout", str(held), "--json"], capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr
    assert json.loads(proc.stdout)["heldout"]["n"] == 2


def test_idf_generic_token_near_zero_unique_token_full_weight(tmp_path):
    rows = [evaluate.prepare(r) for r in evaluate.parse_index(_index(tmp_path))]
    rows = [dict(r, pos=r["pos"] | {"common"}) for r in rows]  # token shared by every row
    idf = evaluate.idf_table(rows)
    n = len(rows)
    assert idf["common"] == pytest.approx(1.0)                      # log(1) + 1: floor only
    assert idf["unweighted"] == pytest.approx(math.log((n + 1) / 2) + 1)  # in one row only
    assert idf["unweighted"] > idf["common"]


def test_phrase_bigram_bonus():
    row = evaluate.prepare({"id": "x.y", "name": "Xy", "signals": "prefix tree; two pointers",
                            "avoid_when": []})
    assert ("prefix", "tree") in row["bigrams"]
    idf = {t: 1.0 for t in row["pos"]}
    adjacent, _, _ = evaluate.score_row(evaluate.tokenize("prefix tree lookup"), row, idf, 1.0)
    apart, _, _ = evaluate.score_row(evaluate.tokenize("tree of prefix"), row, idf, 1.0)
    assert adjacent == pytest.approx(apart + evaluate.PHRASE_BONUS)
