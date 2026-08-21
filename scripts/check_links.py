#!/usr/bin/env python3
"""Check for dead file references in rules/*.md and the two READMEs.

Stdlib only. Two independent checks:
  (a) rules/*.md — every bare `*.md` filename token mentioned in prose must
      exist somewhere under rules/ (base files and rules/customize/ alike).
  (b) README.md / README.zh-TW.md — every markdown relative link `](path)`
      (http(s) links and #anchors skipped) must resolve to a real file,
      relative to the repo root.
"""
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
RULES_DIR = REPO_ROOT / "rules"
AGENT_DOC_DIR = REPO_ROOT / "agent_doc"

# Regex kept deliberately conservative (lowercase filename charset) so it
# doesn't false-positive on placeholders like "X.md" or "<repo>.md". The
# optional leading group captures ONE or TWO directory qualifiers (e.g.
# "agent_doc/eagle-codex-prescreen.md" or the two-level
# "agent_doc/zh_tw/patterns.md" — a language/topic subdir under agent_doc/)
# so path-qualified references can be resolved against that directory
# instead of the bare rules/ basename set. Capped at two levels: agent_doc/
# subdirs are exactly one level deep (install.sh's own constraint), so a
# third segment is never a real path this repo produces.
MD_TOKEN_RE = re.compile(r"\b((?:[a-z0-9_-]+/){1,2})?([a-z0-9-]+\.md)\b")

# Known generic placeholders used in illustrative prose, not real paths.
PLACEHOLDER_TOKENS = {"rules-file.md"}

MD_LINK_RE = re.compile(r"\]\(([^)]+)\)")


def collect_dir_md_basenames(directory: Path) -> set:
    if not directory.is_dir():
        return set()
    return {p.name for p in directory.rglob("*.md")}


def collect_rules_md_basenames() -> set:
    return collect_dir_md_basenames(RULES_DIR)


def collect_agent_doc_subdir_basenames() -> dict:
    """Return {subdir_name: {basenames directly in agent_doc/<subdir>/}} —
    one level deep only, `customize/` included like any other subdir (it
    has its own basename set, just like `zh_tw/`/`en_us/`)."""
    if not AGENT_DOC_DIR.is_dir():
        return {}
    return {
        sub.name: {p.name for p in sub.glob("*.md")}
        for sub in AGENT_DOC_DIR.iterdir()
        if sub.is_dir()
    }


def check_rules_refs() -> list:
    errors = []
    known_basenames = collect_rules_md_basenames()
    known_agent_doc_basenames = collect_dir_md_basenames(AGENT_DOC_DIR)
    known_agent_doc_subdirs = collect_agent_doc_subdir_basenames()
    for path in sorted(RULES_DIR.glob("*.md")):
        text = path.read_text(encoding="utf-8")
        rel = path.relative_to(REPO_ROOT)
        for lineno, line in enumerate(text.splitlines(), start=1):
            for match in MD_TOKEN_RE.finditer(line):
                qualifier_raw, token = match.group(1), match.group(2)
                if "<" in line[max(0, match.start() - 1):match.start()]:
                    continue
                if token in PLACEHOLDER_TOKENS:
                    continue
                segments = qualifier_raw.rstrip("/").split("/") if qualifier_raw else []
                if len(segments) == 2 and segments[0] == "agent_doc":
                    subdir = segments[1]
                    if token not in known_agent_doc_subdirs.get(subdir, set()):
                        errors.append(
                            f"{rel}:{lineno}: referenced '{match.group(0)}' "
                            f"not found under agent_doc/{subdir}/"
                        )
                    continue
                if len(segments) == 1 and segments[0] == "agent_doc":
                    if token not in known_agent_doc_basenames:
                        errors.append(
                            f"{rel}:{lineno}: referenced '{match.group(0)}' "
                            f"not found under agent_doc/"
                        )
                    continue
                if token not in known_basenames:
                    errors.append(
                        f"{rel}:{lineno}: referenced '{token}' not found "
                        f"under {RULES_DIR.relative_to(REPO_ROOT)}/"
                    )
    return errors


def check_readme_links() -> list:
    errors = []
    for name in ("README.md", "README.zh-TW.md"):
        path = REPO_ROOT / name
        if not path.is_file():
            errors.append(f"{name}: file not found")
            continue
        text = path.read_text(encoding="utf-8")
        for lineno, line in enumerate(text.splitlines(), start=1):
            for match in MD_LINK_RE.finditer(line):
                target = match.group(1).strip()
                if target.startswith(("http://", "https://", "#")):
                    continue
                target_path = target.split("#", 1)[0]
                if not target_path:
                    continue
                resolved = REPO_ROOT / target_path
                if not resolved.is_file():
                    errors.append(f"{name}:{lineno}: dead link target '{target}'")
    return errors


def main() -> int:
    errors = check_rules_refs() + check_readme_links()
    if errors:
        print(f"check_links.py: {len(errors)} dead reference(s):")
        for err in errors:
            print(f"  - {err}")
        return 1
    print("check_links.py: OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
