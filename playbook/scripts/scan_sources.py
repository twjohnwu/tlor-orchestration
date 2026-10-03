#!/usr/bin/env python3
"""Inventory the evidence repositories listed in playbook/sources.yaml.

Inputs:  --sources-root DIR (or env PLAYBOOK_SOURCES_ROOT) holding
         Primary/<local_dir> and Secondary/<local_dir> clones; sources.yaml.
Output:  one JSON line per source file in --out (default
         playbook/.build/inventory.jsonl), sorted by (source, path), with
         source, path, language, filename, candidate, category_guess,
         license, commit, size. Per-repo counts go to stderr.

VCS dirs, build outputs, binaries, PDFs and files over 200 KB are skipped.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

import yaml

PLAYBOOK_DIR = Path(__file__).resolve().parent.parent
DEFAULT_SOURCES = PLAYBOOK_DIR / "sources.yaml"
DEFAULT_OUT = PLAYBOOK_DIR / ".build" / "inventory.jsonl"

MAX_FILE_BYTES = 200 * 1024
SKIP_DIRS = {
    ".git", ".hg", ".svn", ".github", ".idea", ".vscode", "node_modules",
    "build", "dist", "out", "target", "bin", "obj", "__pycache__",
    ".gradle", ".bazel", "venv", ".venv",
}
LANGUAGES = {
    ".py": "python",
    ".cpp": "cpp", ".cc": "cpp", ".cxx": "cpp", ".hpp": "cpp", ".h": "cpp",
    ".c": "c",
    ".java": "java",
    ".js": "javascript", ".ts": "typescript",
    ".go": "go", ".rs": "rust", ".cs": "csharp", ".kt": "kotlin",
    ".md": "markdown",
}
TEST_SUFFIX_RE = re.compile(r"(_tests?|_spec)$")
TEST_PREFIX_RE = re.compile(r"^tests?_")
TRAILING_NUM_RE = re.compile(r"(_?\d+)+$")
CAMEL_RE = re.compile(r"(?<=[a-z0-9])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z])")


def normalize(text: str) -> str:
    """Lowercase, split camelCase, map `-`/space/`.` to `_`, collapse runs."""
    text = CAMEL_RE.sub("_", text)
    text = re.sub(r"[-\s.]+", "_", text.lower())
    return re.sub(r"_+", "_", text).strip("_")


def candidate_name(filename: str) -> str:
    """Normalized stem with test markers and trailing numbers removed."""
    stem = normalize(os.path.splitext(filename)[0])
    stem = TEST_SUFFIX_RE.sub("", stem)
    stem = TEST_PREFIX_RE.sub("", stem)
    stripped = TRAILING_NUM_RE.sub("", stem)
    return stripped or stem


def load_sources(path: Path) -> list:
    """Return [(tier, repo_dict)] in file order (primary first)."""
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    out = []
    for tier in ("primary", "secondary"):
        for repo in data.get(tier) or []:
            out.append((tier, repo))
    return out


def repo_root(sources_root: Path, tier: str, repo: dict) -> Path:
    return sources_root / tier.capitalize() / repo["local_dir"]


def head_commit(root: Path):
    """`git rev-parse HEAD` of a clone, or None when it is not a git checkout."""
    if not (root / ".git").exists():
        return None
    try:
        proc = subprocess.run(["git", "-C", str(root), "rev-parse", "HEAD"],
                              stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                              universal_newlines=True)
    except OSError:
        return None
    return proc.stdout.strip() if proc.returncode == 0 else None


def commit_warning(root: Path, repo: dict):
    """A warning string when the clone's HEAD differs from sources.yaml, else None."""
    head = head_commit(root)
    pinned = str(repo.get("commit"))
    if head is None or head == pinned:
        return None
    return "WARNING: %s HEAD %s != sources.yaml commit %s" % (repo["repo"], head, pinned)


def scan_repo(root: Path, repo: dict) -> list:
    rows = []
    for dirpath, dirnames, filenames in os.walk(str(root)):
        dirnames[:] = sorted(d for d in dirnames if d not in SKIP_DIRS)
        for name in sorted(filenames):
            language = LANGUAGES.get(os.path.splitext(name)[1].lower())
            if language is None:
                continue
            full = os.path.join(dirpath, name)
            try:
                size = os.path.getsize(full)
            except OSError:
                continue
            if size > MAX_FILE_BYTES:
                continue
            rel = os.path.relpath(full, str(root)).replace(os.sep, "/")
            top = rel.split("/")[0] if "/" in rel else ""
            rows.append({
                "source": repo["repo"],
                "path": rel,
                "language": language,
                "filename": name,
                "candidate": candidate_name(name),
                "category_guess": normalize(top),
                "license": repo.get("license"),
                "commit": repo.get("commit"),
                "size": size,
            })
    rows.sort(key=lambda r: r["path"])
    return rows


def main(argv: list = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--sources-root",
                        default=os.environ.get("PLAYBOOK_SOURCES_ROOT"),
                        help="dir holding Primary/ and Secondary/ clones "
                             "(env PLAYBOOK_SOURCES_ROOT)")
    parser.add_argument("--sources", default=str(DEFAULT_SOURCES))
    parser.add_argument("--out", default=str(DEFAULT_OUT))
    args = parser.parse_args(argv)
    if not args.sources_root:
        parser.error("--sources-root or PLAYBOOK_SOURCES_ROOT is required")

    sources_root = Path(args.sources_root)
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    total = 0
    with out_path.open("w", encoding="utf-8") as fh:
        for tier, repo in load_sources(Path(args.sources)):
            root = repo_root(sources_root, tier, repo)
            if not root.is_dir():
                print("missing repo dir: %s" % root, file=sys.stderr)
                return 1
            warning = commit_warning(root, repo)
            if warning:
                print(warning, file=sys.stderr)
            rows = scan_repo(root, repo)
            for row in rows:
                fh.write(json.dumps(row, sort_keys=True) + "\n")
            total += len(rows)
            print("%-34s %-9s %6d files" % (repo["repo"], tier, len(rows)),
                  file=sys.stderr)
    print("total %d -> %s" % (total, out_path), file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
