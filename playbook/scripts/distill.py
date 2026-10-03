#!/usr/bin/env python3
"""Build a distillation prompt pack from an evidence bundle, or check an entry.

Needs pyyaml. `--id ID` writes <out-dir>/<id>.md: the distillation rules,
the taxonomy row, the entry template, the metadata schema, the required test
file, then every source's evidence side by side. A gondor-builder dispatch
(not this script) writes the entry from the pack; no LLM is called here.

`--check ENTRY_PATH` verifies the entry has every `## ` section of the entry
template, in the template's order; exit 1 lists the missing/misordered ones.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import yaml

PLAYBOOK_DIR = Path(__file__).resolve().parent.parent
DEFAULT_EVIDENCE_DIR = PLAYBOOK_DIR / ".build" / "evidence"
DEFAULT_OUT_DIR = PLAYBOOK_DIR / ".build" / "prompts"
DEFAULT_TAXONOMY = PLAYBOOK_DIR / "taxonomy" / "algorithms.yaml"
TEMPLATE_PATH = PLAYBOOK_DIR / "templates" / "entry.md"
METADATA_EXAMPLE = PLAYBOOK_DIR / "metadata" / "algorithms" / "_example.yaml.txt"

TEST_CLASSES = (
    ("TestUnit", "typical inputs, expected outputs"),
    ("TestEdge", "empty, single element, duplicates, boundaries"),
    ("TestKnownExample", "one worked example from the entry or a source"),
    ("TestPreconditionReject", "each violated precondition raises ValueError"),
)

RULES = """\
## 1. Distillation rules

- Compare ALL sources below before writing; never summarize one repo.
  Note where they agree, where one adds an edge case or variant, and where
  they conflict.
- Confidence: two or more primary sources agreeing -> `confidence: high`;
  one primary source -> `confidence: medium`; secondary-only or conflicting
  sources -> `review_required: true`, and name the conflict in the entry
  (Common Failure Modes or Variants).
- The Canonical Implementation is a REWRITE in Python 3.7-compatible code
  (`from __future__ import annotations`; no walrus, no `X | Y` types, no
  `match`), not a copy of any source.
- Every source you used must appear in both Sources and License Provenance
  with repo, path, commit and license exactly as in the evidence headings.
- Secondary sources add variants and edge cases; they never decide alone.
- Write three files: the entry, its metadata twin, and the tests. Do not
  invent facts the evidence does not support.
"""


def taxonomy_row(taxonomy_path: Path, algo_id: str):
    data = yaml.safe_load(taxonomy_path.read_text(encoding="utf-8"))
    for row in data.get("algorithms", []):
        if row.get("id") == algo_id:
            return row
    return None


def test_file_path(algo_id: str) -> str:
    return "tests/playbook/algorithms/test_%s.py" % algo_id.replace(".", "_")


def template_sections(template_text: str) -> list:
    """`## ` headings of the template, in order, skipping fenced blocks."""
    return entry_headings(template_text)


def entry_headings(text: str) -> list:
    headings = []
    in_fence = False
    for line in text.splitlines():
        if line.startswith("```"):
            in_fence = not in_fence
        elif not in_fence and line.startswith("## "):
            headings.append(line.strip())
    return headings


def check_sections(entry_text: str, template_text: str) -> list:
    """Return problem strings; empty means every section present, in order."""
    required = template_sections(template_text)
    found = entry_headings(entry_text)
    problems = []
    for heading in required:
        if heading not in found:
            problems.append("missing section: %s" % heading)
    present = [h for h in found if h in required]
    expected = [h for h in required if h in present]
    if present != expected:
        for got, want in zip(present, expected):
            if got != want:
                problems.append("misordered section: found '%s' where '%s' belongs" % (got, want))
                break
    return problems


def render_evidence(sources: list) -> str:
    parts = ["## 6. Evidence\n"]
    for src in sources:
        parts.append("### %s — %s — %s @ %s\n" % (
            src.get("tier", "?"), src["repo"], src["path"], src["commit"][:10]))
        parts.append("License: %s; language: %s\n" % (src.get("license"), src.get("language")))
        parts.append("README excerpt:\n\n%s\n" % (src.get("readme_excerpt") or "(none)"))
        parts.append("Comments / docstring:\n\n%s\n" % (src.get("comments_or_docstring") or "(none)"))
        note = " (truncated)" if src.get("code_truncated") else ""
        parts.append("Code%s:\n\n````\n%s\n````\n" % (note, src.get("code", "")))
        tests = src.get("tests") or []
        if tests:
            parts.append("Tests:\n")
            for t in tests:
                parts.append("`%s`\n\n````\n%s\n````\n" % (t.get("path", "?"), t.get("text", "")))
        else:
            parts.append("Tests: (none)\n")
    return "\n".join(parts)


def build_pack(evidence: dict, row, template_text: str, metadata_text: str) -> str:
    algo_id = evidence["id"]
    if row:
        tax = "id: %s\nname: %s\ncategory: %s\naliases: %s\nrelated: %s" % (
            row["id"], row["name"], row["category"], row.get("aliases", []), row.get("related", []))
    else:
        tax = "id: %s\nname: %s\n(no taxonomy row found)" % (algo_id, evidence.get("name", ""))
    test_rows = "\n".join("- `%s` — %s" % c for c in TEST_CLASSES)
    return "\n".join([
        "# Prompt pack: %s\n" % algo_id,
        RULES,
        "## 2. Taxonomy row\n\n```yaml\n%s\n```\n" % tax,
        "## 3. Entry template (use verbatim; write to `agent_doc/algorithms/%s.md`)\n\n"
        "`````markdown\n%s\n`````\n" % (algo_id, template_text.rstrip("\n")),
        "## 4. Metadata schema\n\n`playbook/metadata/algorithms/%s.yaml` must mirror the entry "
        "frontmatter (id, name, category, confidence, review_required, sources) and add "
        "signals, preconditions, avoid_when, complexity, related, aliases.\n\n"
        "```yaml\n%s\n```\n" % (algo_id, metadata_text.rstrip("\n")),
        "## 5. Required tests\n\nFile: `%s`. Load the implementation with "
        "`from ._load import load_impl; impl = load_impl(\"%s\")`. Four mandatory "
        "test classes:\n\n%s\n" % (test_file_path(algo_id), algo_id, test_rows),
        render_evidence(evidence["sources"]),
    ])


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--id", dest="algo_id")
    parser.add_argument("--check", type=Path, metavar="ENTRY_PATH")
    parser.add_argument("--evidence-dir", type=Path, default=DEFAULT_EVIDENCE_DIR)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--taxonomy", type=Path, default=DEFAULT_TAXONOMY)
    args = parser.parse_args()

    if args.check:
        if not args.check.is_file():
            print("distill: no such entry: %s" % args.check, file=sys.stderr)
            return 1
        problems = check_sections(args.check.read_text(encoding="utf-8"),
                                  TEMPLATE_PATH.read_text(encoding="utf-8"))
        for p in problems:
            print("distill: %s: %s" % (args.check.name, p), file=sys.stderr)
        if not problems:
            print("distill: %s has all sections in order" % args.check.name)
        return 1 if problems else 0

    if not args.algo_id:
        parser.error("one of --id or --check is required")
    evidence_path = args.evidence_dir / ("%s.json" % args.algo_id)
    if not evidence_path.is_file():
        print("distill: no evidence bundle %s; run extract_candidates.py first" % evidence_path,
              file=sys.stderr)
        return 1
    evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
    if not evidence.get("sources"):
        print("distill: %s has no sources; nothing to distill" % evidence_path, file=sys.stderr)
        return 1
    pack = build_pack(evidence, taxonomy_row(args.taxonomy, args.algo_id),
                      TEMPLATE_PATH.read_text(encoding="utf-8"),
                      METADATA_EXAMPLE.read_text(encoding="utf-8"))
    args.out_dir.mkdir(parents=True, exist_ok=True)
    out = args.out_dir / ("%s.md" % args.algo_id)
    out.write_text(pack, encoding="utf-8")
    print("distill: wrote %s (%.1f KB, %d sources)" % (out, len(pack.encode("utf-8")) / 1024.0,
                                                     len(evidence["sources"])))
    return 0


if __name__ == "__main__":
    sys.exit(main())
