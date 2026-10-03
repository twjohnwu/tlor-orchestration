#!/usr/bin/env python3
"""Bundle per-algorithm evidence from the source repositories.

Inputs:  --sources-root DIR (or env PLAYBOOK_SOURCES_ROOT), the inventory
         written by scan_sources.py, the taxonomy (aliases per id), and
         sources.yaml (tier per repo).
Output:  <out-dir>/<id>.json per requested id (default
         playbook/.build/evidence): id, name, sources[] with repo, path,
         commit, license, language, tier, code (capped at 20 KB, with
         code_truncated), comments_or_docstring, readme_excerpt (<=2 KB or
         null) and tests; plus unmatched_hint when no primary file matched.

Matching: exact normalized candidate == alias first, then alias as a
substring of the normalized path. At most 4 files per repo per id, exact
matches first. Test files are never matched as code; a test file whose
candidate name equals a matched code file's is attached to it.
"""
from __future__ import annotations

import argparse
import ast
import json
import os
import re
import sys
from pathlib import Path

import yaml

import scan_sources
from scan_sources import normalize

PLAYBOOK_DIR = scan_sources.PLAYBOOK_DIR
DEFAULT_TAXONOMY = PLAYBOOK_DIR / "taxonomy" / "algorithms.yaml"
DEFAULT_INVENTORY = scan_sources.DEFAULT_OUT
DEFAULT_OUT_DIR = PLAYBOOK_DIR / ".build" / "evidence"

CODE_CAP = 20 * 1024
TESTS_CAP = 10 * 1024
README_CAP = 2 * 1024
COMMENT_CAP = 2 * 1024
MAX_FILES_PER_REPO = 4

TEST_FILE_RE = re.compile(r"(^test_|_tests?\.|tests?\.[a-z]+$|test\.[a-z]+$)", re.I)
TEST_DIRS = {"test", "tests"}
BLOCK_COMMENT_RE = re.compile(r"/\*.*?\*/", re.S)


def is_test_path(path: str) -> bool:
    parts = path.split("/")
    return bool(TEST_FILE_RE.search(parts[-1])) or any(
        p.lower() in TEST_DIRS for p in parts[:-1])


def read_text(path: Path, cap: int):
    """Return (text, truncated); undecodable bytes are replaced."""
    raw = path.read_bytes()
    truncated = len(raw) > cap
    return raw[:cap].decode("utf-8", "replace"), truncated


def match_rank(row: dict, aliases: list):
    """0 exact candidate match, 1 path substring match, None no match."""
    if row["candidate"] in aliases:
        return 0
    norm_path = normalize(row["path"].replace("/", " "))
    for alias in aliases:
        if alias in norm_path:
            return 1
    return None


def select_files(rows: list, aliases: list) -> list:
    """Pick up to MAX_FILES_PER_REPO code rows, best match first."""
    ranked = []
    for row in rows:
        if row["language"] == "markdown" or is_test_path(row["path"]):
            continue
        rank = match_rank(row, aliases)
        if rank is not None:
            ranked.append((rank, len(row["candidate"]), row["path"], row))
    ranked.sort(key=lambda t: t[:3])
    return [t[3] for t in ranked[:MAX_FILES_PER_REPO]]


def extract_comments(text: str, language: str) -> str:
    """Best-effort leading docs: Python docstring, else comment blocks."""
    found = ""
    if language == "python":
        try:
            found = ast.get_docstring(ast.parse(text)) or ""
        except (SyntaxError, ValueError):
            found = ""
        if not found:
            lines = []
            for line in text.splitlines():
                if line.startswith("#") and not line.startswith("#!"):
                    lines.append(line.lstrip("#").strip())
                elif lines or line.strip():
                    break
            found = "\n".join(lines)
    else:
        blocks = BLOCK_COMMENT_RE.findall(text)[:3]
        found = "\n".join(blocks)
        if not found:
            lines = []
            for line in text.splitlines():
                if line.strip().startswith("//"):
                    lines.append(line.strip().lstrip("/").strip())
                elif lines:
                    break
            found = "\n".join(lines)
    return found[:COMMENT_CAP]


def readme_excerpt(root: Path, rel_path: str, aliases: list):
    """Nearest README section (walking up) mentioning an alias, <=2 KB."""
    words = [a.replace("_", " ") for a in aliases]
    directory = os.path.dirname(rel_path)
    while True:
        readme = root / directory / "README.md"
        if readme.is_file():
            text, _ = read_text(readme, 200 * 1024)
            sections = re.split(r"(?m)^(?=#{1,6} )", text)
            for section in sections:
                lowered = normalize_loose(section)
                if any(w in lowered for w in words):
                    return section.strip()[:README_CAP]
        if not directory:
            return None
        directory = os.path.dirname(directory)


def normalize_loose(text: str) -> str:
    return re.sub(r"[-_\s]+", " ", text.lower())


def find_tests(root: Path, rows: list, code_row: dict) -> list:
    """Test files whose candidate name equals the code file's (e.g. FooTest)."""
    out = []
    budget = TESTS_CAP
    for row in rows:
        if row["language"] == "markdown" or not is_test_path(row["path"]):
            continue
        if row["candidate"] != code_row["candidate"]:
            continue
        text, _ = read_text(root / row["path"], max(budget, 0))
        out.append({"path": row["path"], "text": text})
        budget -= len(text.encode("utf-8"))
        if budget <= 0:
            break
    return out


def build_evidence(entry: dict, inventory: list, sources: list,
                   sources_root: Path) -> dict:
    aliases = sorted(set(normalize(a) for a in entry.get("aliases") or []))
    by_repo = {}
    for row in inventory:
        by_repo.setdefault(row["source"], []).append(row)
    bundle = {"id": entry["id"], "name": entry["name"], "sources": []}
    primary_hits = 0
    for tier, repo in sources:
        rows = by_repo.get(repo["repo"], [])
        root = scan_sources.repo_root(sources_root, tier, repo)
        for row in select_files(rows, aliases):
            text, truncated = read_text(root / row["path"], CODE_CAP)
            bundle["sources"].append({
                "repo": repo["repo"],
                "path": row["path"],
                "commit": row["commit"],
                "license": row["license"],
                "language": row["language"],
                "tier": tier,
                "code": text,
                "code_truncated": truncated,
                "comments_or_docstring": extract_comments(text, row["language"]),
                "readme_excerpt": readme_excerpt(root, row["path"], aliases),
                "tests": find_tests(root, rows, row),
            })
            if tier == "primary":
                primary_hits += 1
    if primary_hits == 0:
        bundle["unmatched_hint"] = (
            "no primary-source file matched aliases %s; add aliases to the "
            "taxonomy entry and rerun" % aliases)
    return bundle


def main(argv: list = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--sources-root",
                        default=os.environ.get("PLAYBOOK_SOURCES_ROOT"))
    parser.add_argument("--sources", default=str(scan_sources.DEFAULT_SOURCES))
    parser.add_argument("--inventory", default=str(DEFAULT_INVENTORY))
    parser.add_argument("--taxonomy", default=str(DEFAULT_TAXONOMY))
    parser.add_argument("--id", action="append", default=[], dest="ids")
    parser.add_argument("--all", action="store_true",
                        help="process every taxonomy id")
    parser.add_argument("--out-dir", default=str(DEFAULT_OUT_DIR))
    args = parser.parse_args(argv)
    if not args.sources_root:
        parser.error("--sources-root or PLAYBOOK_SOURCES_ROOT is required")
    if not args.ids and not args.all:
        parser.error("give --id ID (repeatable) or --all")

    taxonomy = yaml.safe_load(Path(args.taxonomy).read_text(encoding="utf-8"))
    entries = {e["id"]: e for e in taxonomy["algorithms"]}
    wanted = list(entries) if args.all else args.ids
    unknown = [i for i in wanted if i not in entries]
    if unknown:
        print("unknown id(s): %s" % ", ".join(unknown), file=sys.stderr)
        return 1

    with open(args.inventory, encoding="utf-8") as fh:
        inventory = [json.loads(line) for line in fh if line.strip()]
    sources = scan_sources.load_sources(Path(args.sources))
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    for algo_id in wanted:
        bundle = build_evidence(entries[algo_id], inventory, sources,
                                Path(args.sources_root))
        (out_dir / (algo_id + ".json")).write_text(
            json.dumps(bundle, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8")
        counts = {"primary": 0, "secondary": 0}
        for src in bundle["sources"]:
            counts[src["tier"]] += 1
        print("%s: primary=%d secondary=%d" % (
            algo_id, counts["primary"], counts["secondary"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
