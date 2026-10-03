#!/usr/bin/env python3
"""Build agent_doc/algorithms/INDEX.md from playbook/metadata/algorithms/*.yaml.

Needs pyyaml. INDEX.md is the only retrieval surface agents get (Grep over
one row per algorithm), so the output is deterministic: rows sorted by id,
no timestamps. Fails loudly (exit 1) naming the file and field on bad
metadata, and on an empty metadata dir.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
DEFAULT_METADATA_DIR = REPO_ROOT / "playbook" / "metadata" / "algorithms"
DEFAULT_OUT = REPO_ROOT / "agent_doc" / "algorithms" / "INDEX.md"

REQUIRED_STR_FIELDS = ("id", "name", "confidence")
REQUIRED_LIST_FIELDS = ("signals", "avoid_when")

HEADER = """\
<!-- GENERATED FILE - do not edit. Regenerate: python3 playbook/scripts/build_index.py -->
# Algorithm INDEX

Generated from `playbook/metadata/algorithms/*.yaml`; regenerate with `python3 playbook/scripts/build_index.py`.
Retrieval: Grep this table for the problem's signal words, then Read the matching entry; see README.md.

| id | name | signals | avoid_when | confidence |
|---|---|---|---|---|
"""


class MetadataError(Exception):
    pass


def cell(text: str) -> str:
    return " ".join(str(text).split()).replace("|", "\\|")


def load_entry(path: Path) -> dict:
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise MetadataError("%s: invalid YAML: %s" % (path.name, exc))
    if not isinstance(data, dict):
        raise MetadataError("%s: top level must be a mapping" % path.name)
    for field in REQUIRED_STR_FIELDS:
        if not isinstance(data.get(field), str) or not data[field].strip():
            raise MetadataError("%s: missing or empty field '%s'" % (path.name, field))
    for field in REQUIRED_LIST_FIELDS:
        value = data.get(field)
        if not isinstance(value, list) or not all(isinstance(v, str) for v in value):
            raise MetadataError("%s: field '%s' must be a list of strings" % (path.name, field))
    if not data["signals"]:
        raise MetadataError("%s: field 'signals' must not be empty" % path.name)
    if path.stem != data["id"]:
        raise MetadataError("%s: field 'id' (%s) must match the file name" % (path.name, data["id"]))
    if not isinstance(data.get("review_required", False), bool):
        raise MetadataError("%s: field 'review_required' must be true or false" % path.name)
    return data


def build_rows(entries: list) -> str:
    lines = []
    for e in sorted(entries, key=lambda x: x["id"]):
        confidence = cell(e["confidence"])
        if e.get("review_required", False):
            confidence += " ⚠ review"
        lines.append("| %s | %s | %s | %s | %s |" % (
            cell(e["id"]),
            cell(e["name"]),
            cell("; ".join(e["signals"])),
            cell("; ".join(e["avoid_when"])),
            confidence,
        ))
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--metadata-dir", type=Path, default=DEFAULT_METADATA_DIR)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()

    files = sorted(args.metadata_dir.glob("*.yaml")) if args.metadata_dir.is_dir() else []
    if not files:
        print("build_index: no *.yaml metadata files in %s; nothing to index" % args.metadata_dir,
              file=sys.stderr)
        return 1
    try:
        entries = [load_entry(f) for f in files]
    except MetadataError as exc:
        print("build_index: %s" % exc, file=sys.stderr)
        return 1
    seen = set()
    for e in entries:
        if e["id"] in seen:
            print("build_index: duplicate id %s" % e["id"], file=sys.stderr)
            return 1
        seen.add(e["id"])

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(HEADER + build_rows(entries), encoding="utf-8")
    print("build_index: wrote %d rows to %s" % (len(entries), args.out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
