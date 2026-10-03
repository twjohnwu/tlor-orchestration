#!/usr/bin/env python3
"""Check that an algorithm entry, its metadata twin and its tests agree.

Needs pyyaml. Per id, prints one PASS/FAIL line per named check: frontmatter
vs file name and metadata, section order (distill.check_sections), exactly one
Python block under Canonical Implementation that compiles and is 3.7-safe,
License Provenance rows present in sources.yaml, non-empty signals/avoid_when,
and optionally the entry's tests. Exit 1 if any check fails. `--all` walks
every entry in --entries-dir except README.md and INDEX.md.
"""
from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from pathlib import Path

import yaml

import distill

REPO_ROOT = distill.PLAYBOOK_DIR.parent
PLAYBOOK_DIR = distill.PLAYBOOK_DIR
DEFAULT_ENTRIES_DIR = REPO_ROOT / "agent_doc" / "algorithms"
DEFAULT_METADATA_DIR = PLAYBOOK_DIR / "metadata" / "algorithms"
DEFAULT_SOURCES = PLAYBOOK_DIR / "sources.yaml"
DEFAULT_IMPL_DIR = PLAYBOOK_DIR / ".build" / "impl"
DEFAULT_TESTS_DIR = REPO_ROOT / "tests" / "playbook" / "algorithms"

MIRRORED_FIELDS = ("name", "category", "confidence", "review_required", "sources")
SKIP_FILES = ("README.md", "INDEX.md")
FRONTMATTER_RE = re.compile(r"\A---\n(.*?)\n---\n", re.S)
PY_BLOCK_RE = re.compile(r"^```python[ \t]*\n(.*?)^```[ \t]*$", re.S | re.M)
WALRUS_RE = re.compile(r":=")
MATCH_RE = re.compile(r"^\s*match\s+.+:\s*$", re.M)
# `-> int | None` and `x: int | None` annotation segments
ANNOTATION_UNION_RE = re.compile(r"(->|[A-Za-z_]\w*\s*:)\s*[^=\n,)]*\|")


def split_frontmatter(text: str):
    m = FRONTMATTER_RE.match(text)
    if not m:
        return None
    try:
        data = yaml.safe_load(m.group(1))
    except yaml.YAMLError:
        return None
    return data if isinstance(data, dict) else None


def section_body(text: str, heading: str) -> str:
    out = []
    capture = False
    in_fence = False
    for line in text.splitlines():
        if line.startswith("```"):
            in_fence = not in_fence
        if not in_fence and line.startswith("## "):
            capture = line.strip() == heading
            continue
        if capture:
            out.append(line)
    return "\n".join(out)


def provenance_rows(text: str) -> list:
    rows = []
    for line in section_body(text, "## License Provenance").splitlines():
        line = line.strip()
        if not line.startswith("|"):
            continue
        cells = [c.strip().strip("`") for c in line.strip("|").split("|")]
        if len(cells) < 4 or cells[0] == "repository" or set(cells[0]) <= set("-: "):
            continue
        rows.append(cells)
    return rows


def known_commits(sources_path: Path) -> set:
    data = yaml.safe_load(sources_path.read_text(encoding="utf-8")) or {}
    known = set()
    for tier in ("primary", "secondary"):
        for src in data.get(tier, []) or []:
            known.add((src["repo"], str(src["commit"])))
    return known


def py37_problems(code: str) -> list:
    problems = []
    if WALRUS_RE.search(code):
        problems.append("walrus operator ':='")
    if MATCH_RE.search(code):
        problems.append("'match' statement")
    if ANNOTATION_UNION_RE.search(code):
        problems.append("'X | Y' in an annotation")
    return problems


class Report:
    def __init__(self):
        self.failed = False

    def line(self, ok: bool, name: str, detail: str = "") -> None:
        if not ok:
            self.failed = True
        print("%s %s%s" % ("PASS" if ok else "FAIL", name, (": " + detail) if detail else ""))


def validate_id(algo_id: str, args, report: Report) -> None:
    stem = algo_id.replace(".", "_")
    entry_path = args.entries_dir / ("%s.md" % algo_id)
    meta_path = args.metadata_dir / ("%s.yaml" % algo_id)
    print("== %s" % algo_id)
    if not entry_path.is_file():
        report.line(False, "entry exists", str(entry_path))
        return
    text = entry_path.read_text(encoding="utf-8")
    front = split_frontmatter(text)
    report.line(front is not None, "frontmatter parses")
    front = front or {}
    meta = None
    if meta_path.is_file():
        try:
            meta = yaml.safe_load(meta_path.read_text(encoding="utf-8"))
        except yaml.YAMLError as exc:
            report.line(False, "metadata parses", str(exc))
        else:
            report.line(isinstance(meta, dict), "metadata parses")
            meta = meta if isinstance(meta, dict) else None
    else:
        report.line(False, "metadata parses", "missing %s" % meta_path)
    meta = meta or {}

    bad = [n for n, v in (("frontmatter", front.get("id")), ("metadata", meta.get("id"))) if v != algo_id]
    report.line(not bad, "id matches file name", ("mismatch in " + ", ".join(bad)) if bad else "")
    for field in MIRRORED_FIELDS:
        same = field in front and front.get(field) == meta.get(field)
        report.line(same, "metadata.%s equals frontmatter" % field,
                    "" if same else "frontmatter=%r metadata=%r" % (front.get(field), meta.get(field)))

    problems = distill.check_sections(text, distill.TEMPLATE_PATH.read_text(encoding="utf-8"))
    report.line(not problems, "sections complete and in order", "; ".join(problems))

    blocks = PY_BLOCK_RE.findall(section_body(text, "## Canonical Implementation"))
    report.line(len(blocks) == 1, "exactly one python block in Canonical Implementation",
                "found %d" % len(blocks))
    if len(blocks) == 1:
        code = blocks[0]
        try:
            compile(code, "%s.py" % stem, "exec")
            report.line(True, "python block compiles")
        except SyntaxError as exc:
            report.line(False, "python block compiles", str(exc))
        issues = py37_problems(code)
        report.line(not issues, "python block is 3.7-compatible", ", ".join(issues))
        args.impl_dir.mkdir(parents=True, exist_ok=True)
        (args.impl_dir / ("%s.py" % stem)).write_text(code, encoding="utf-8")

    rows = provenance_rows(text)
    report.line(bool(rows), "license provenance has rows")
    known = known_commits(args.sources)
    unknown = ["%s@%s" % (r[0], r[2][:10]) for r in rows if (r[0], r[2]) not in known]
    report.line(not unknown, "provenance repo+commit in sources.yaml", ", ".join(unknown))

    for field in ("signals", "avoid_when"):
        value = meta.get(field)
        report.line(isinstance(value, list) and bool(value), "metadata.%s non-empty" % field)

    if args.run_tests:
        test_path = args.tests_dir / ("test_%s.py" % stem)
        if not test_path.is_file():
            report.line(False, "tests pass", "missing %s" % test_path)
            return
        env = dict(os.environ, PLAYBOOK_IMPL_DIR=str(args.impl_dir.resolve()))
        proc = subprocess.run([sys.executable, "-m", "pytest", "-q", str(test_path)],
                              cwd=str(REPO_ROOT), env=env, stdout=subprocess.PIPE,
                              stderr=subprocess.STDOUT, universal_newlines=True)
        tail = proc.stdout.strip().splitlines()[-1:] or [""]
        report.line(proc.returncode == 0, "tests pass", tail[0])


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--id", dest="algo_id")
    parser.add_argument("--all", action="store_true")
    parser.add_argument("--entries-dir", type=Path, default=DEFAULT_ENTRIES_DIR)
    parser.add_argument("--metadata-dir", type=Path, default=DEFAULT_METADATA_DIR)
    parser.add_argument("--sources", type=Path, default=DEFAULT_SOURCES)
    parser.add_argument("--impl-dir", type=Path, default=DEFAULT_IMPL_DIR)
    parser.add_argument("--tests-dir", type=Path, default=DEFAULT_TESTS_DIR)
    parser.add_argument("--run-tests", action="store_true")
    args = parser.parse_args()

    if args.all:
        ids = sorted(p.stem for p in args.entries_dir.glob("*.md") if p.name not in SKIP_FILES) \
            if args.entries_dir.is_dir() else []
        if not ids:
            print("validate: no entries found in %s" % args.entries_dir)
            return 0
    elif args.algo_id:
        ids = [args.algo_id]
    else:
        parser.error("one of --id or --all is required")

    report = Report()
    for algo_id in ids:
        validate_id(algo_id, args, report)
    return 1 if report.failed else 0


if __name__ == "__main__":
    sys.exit(main())
