# -*- coding: utf-8 -*-
"""Tests for playbook/scripts/distill.py and validate.py.

Every path is a CLI argument, so tests build synthetic entry/metadata/test
trios under tmp_path; the real playbook/ content is only used for the
template and the metadata example.
"""
import importlib
import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
SCRIPTS_DIR = REPO_ROOT / "playbook" / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

distill = importlib.import_module("distill")
validate = importlib.import_module("validate")

COMMIT = "ef2ecc4d34d17ce6249ba5d3f3c17822dfd7bd50"
GOOD_CODE = '''\
from __future__ import annotations


def double(x: int) -> int:
    if x < 0:
        raise ValueError("x must be non-negative")
    return x * 2
'''
FRONT = """\
---
id: demo.double
name: Doubler
category: [demo]
confidence: %s
review_required: false
sources:
  - repo: o/r
    path: a.py
    commit: %s
    license: MIT
---
""" % ("%s", COMMIT)
META = """\
id: demo.double
name: Doubler
category: [demo]
confidence: %s
review_required: false
signals: [double]
avoid_when: [never]
sources:
  - repo: o/r
    path: a.py
    commit: %s
    license: MIT
""" % ("%s", COMMIT)
SOURCES = """\
primary:
  - repo: o/r
    url: https://example.invalid/o/r
    local_dir: o-r
    commit: %s
    license: MIT
    languages: [python]
secondary: []
""" % COMMIT
TEST = """\
import sys

sys.path.insert(0, %r)
from algorithms._load import load_impl


def test_double():
    assert load_impl("demo.double").double(2) == 4
""" % str(REPO_ROOT / "tests" / "playbook")


def make_entry(code=GOOD_CODE, confidence="high", drop=None):
    template = distill.TEMPLATE_PATH.read_text(encoding="utf-8")
    sections = distill.template_sections(template)
    parts = [FRONT % confidence, "# Doubler\n"]
    for heading in sections:
        if heading == drop:
            continue
        if heading == "## Canonical Implementation":
            parts.append("%s\n```python\n%s```\n" % (heading, code))
        elif heading == "## License Provenance":
            parts.append("%s\n| repository | path | commit | license |\n|---|---|---|---|\n"
                         "| o/r | a.py | %s | MIT |\n" % (heading, COMMIT))
        else:
            parts.append("%s\n- x\n" % heading)
    return "\n".join(parts)


@pytest.fixture
def trio(tmp_path):
    (tmp_path / "entries").mkdir()
    (tmp_path / "meta").mkdir()
    (tmp_path / "tests").mkdir()
    (tmp_path / "entries" / "demo.double.md").write_text(make_entry(), encoding="utf-8")
    (tmp_path / "meta" / "demo.double.yaml").write_text(META % "high", encoding="utf-8")
    (tmp_path / "sources.yaml").write_text(SOURCES, encoding="utf-8")
    (tmp_path / "tests" / "test_demo_double.py").write_text(TEST, encoding="utf-8")
    return tmp_path


def run_validate(root, *extra):
    cmd = [sys.executable, str(SCRIPTS_DIR / "validate.py"), "--id", "demo.double",
           "--entries-dir", str(root / "entries"), "--metadata-dir", str(root / "meta"),
           "--sources", str(root / "sources.yaml"), "--impl-dir", str(root / "impl"),
           "--tests-dir", str(root / "tests")] + list(extra)
    return subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                          universal_newlines=True)


def test_correct_trio_passes(trio):
    proc = run_validate(trio)
    assert proc.returncode == 0, proc.stdout
    assert "FAIL" not in proc.stdout
    assert (trio / "impl" / "demo_double.py").is_file()


def test_confidence_mismatch_names_field(trio):
    (trio / "meta" / "demo.double.yaml").write_text(META % "medium", encoding="utf-8")
    proc = run_validate(trio)
    assert proc.returncode == 1
    assert "FAIL metadata.confidence equals frontmatter" in proc.stdout


def test_walrus_fails(trio):
    code = GOOD_CODE.replace("    return x * 2", "    if (y := x * 2):\n        return y\n    return 0")
    (trio / "entries" / "demo.double.md").write_text(make_entry(code=code), encoding="utf-8")
    proc = run_validate(trio)
    assert proc.returncode == 1
    assert "FAIL python block is 3.7-compatible" in proc.stdout


@pytest.mark.skipif(sys.version_info < (3, 8), reason="feature_version check needs 3.8+")
def test_positional_only_params_fail(trio):
    code = GOOD_CODE.replace("def double(x: int)", "def double(x: int, /)")
    (trio / "entries" / "demo.double.md").write_text(make_entry(code=code), encoding="utf-8")
    proc = run_validate(trio)
    assert proc.returncode == 1
    assert "FAIL python block is 3.7-compatible" in proc.stdout


def test_union_annotation_fails(trio):
    code = GOOD_CODE.replace("-> int:", "-> int | None:")
    (trio / "entries" / "demo.double.md").write_text(make_entry(code=code), encoding="utf-8")
    assert "FAIL python block is 3.7-compatible" in run_validate(trio).stdout


def test_unknown_commit_fails(trio):
    text = (trio / "entries" / "demo.double.md").read_text(encoding="utf-8")
    (trio / "entries" / "demo.double.md").write_text(
        text.replace("| o/r | a.py | %s |" % COMMIT, "| o/r | a.py | %s |" % ("0" * 40)),
        encoding="utf-8")
    assert "FAIL provenance repo+commit in sources.yaml" in run_validate(trio).stdout


def test_run_tests_executes_fixture_test(trio):
    proc = run_validate(trio, "--run-tests")
    assert proc.returncode == 0, proc.stdout
    assert "PASS tests pass: 1 passed" in proc.stdout


def test_run_tests_reports_failure(trio):
    (trio / "tests" / "test_demo_double.py").write_text(
        TEST.replace("== 4", "== 5"), encoding="utf-8")
    proc = run_validate(trio, "--run-tests")
    assert proc.returncode == 1
    assert "FAIL tests pass" in proc.stdout


def test_all_with_no_entries_exits_zero(tmp_path):
    (tmp_path / "entries").mkdir()
    (tmp_path / "entries" / "README.md").write_text("x", encoding="utf-8")
    proc = subprocess.run([sys.executable, str(SCRIPTS_DIR / "validate.py"), "--all",
                           "--entries-dir", str(tmp_path / "entries")],
                          stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                          universal_newlines=True)
    assert proc.returncode == 0
    assert "no entries found" in proc.stdout


def test_check_flags_missing_section(tmp_path):
    entry = tmp_path / "e.md"
    entry.write_text(make_entry(drop="## Variants"), encoding="utf-8")
    proc = subprocess.run([sys.executable, str(SCRIPTS_DIR / "distill.py"), "--check", str(entry)],
                          stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                          universal_newlines=True)
    assert proc.returncode == 1
    assert "missing section: ## Variants" in proc.stdout


def test_check_flags_misordered_section(tmp_path):
    text = make_entry()
    a, b = "## Complexity", "## Variants"
    swapped = text.replace(a, "@@").replace(b, a).replace("@@", b)
    problems = distill.check_sections(swapped, distill.TEMPLATE_PATH.read_text(encoding="utf-8"))
    assert any(p.startswith("misordered") for p in problems)


def test_check_accepts_complete_entry():
    assert distill.check_sections(make_entry(), distill.TEMPLATE_PATH.read_text(encoding="utf-8")) == []


def test_distill_pack_has_all_parts(tmp_path):
    ev = tmp_path / "ev"
    ev.mkdir()
    (ev / "demo.double.json").write_text(json.dumps({
        "id": "demo.double", "name": "Doubler",
        "sources": [{"repo": "o/r", "path": "a.py", "commit": COMMIT, "license": "MIT",
                     "language": "python", "tier": "primary", "code": "def f(): pass",
                     "code_truncated": False, "comments_or_docstring": "doc",
                     "readme_excerpt": None,
                     "tests": [{"path": "t.py", "text": "assert 1"}]}]}), encoding="utf-8")
    tax = tmp_path / "tax.yaml"
    tax.write_text("algorithms:\n  - {id: demo.double, name: Doubler, category: [demo], "
                   "aliases: [dbl], related: []}\n", encoding="utf-8")
    out = tmp_path / "out"
    proc = subprocess.run([sys.executable, str(SCRIPTS_DIR / "distill.py"), "--id", "demo.double",
                           "--evidence-dir", str(ev), "--out-dir", str(out), "--taxonomy", str(tax)],
                          stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                          universal_newlines=True)
    assert proc.returncode == 0, proc.stdout
    pack = (out / "demo.double.md").read_text(encoding="utf-8")
    for needle in ("## 1. Distillation rules", "## 2. Taxonomy row", "## 3. Entry template",
                   "## 4. Metadata schema", "## 5. Required tests", "## 6. Evidence",
                   "tests/playbook/algorithms/test_demo_double.py", "TestPreconditionReject",
                   "### primary — o/r — a.py @ ef2ecc4d34", "## License Provenance"):
        assert needle in pack, needle


def test_distill_missing_evidence_exits_one(tmp_path):
    proc = subprocess.run([sys.executable, str(SCRIPTS_DIR / "distill.py"), "--id", "x.y",
                           "--evidence-dir", str(tmp_path)],
                          stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                          universal_newlines=True)
    assert proc.returncode == 1
