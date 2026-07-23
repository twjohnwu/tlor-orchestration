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

# Regex kept deliberately conservative (lowercase filename charset) so it
# doesn't false-positive on placeholders like "X.md" or "<repo>.md".
MD_TOKEN_RE = re.compile(r"\b[a-z0-9-]+\.md\b")

# Known generic placeholders used in illustrative prose, not real paths.
PLACEHOLDER_TOKENS = {"rules-file.md"}

MD_LINK_RE = re.compile(r"\]\(([^)]+)\)")


def collect_rules_md_basenames() -> set:
    return {p.name for p in RULES_DIR.rglob("*.md")}


def check_rules_refs() -> list:
    errors = []
    known_basenames = collect_rules_md_basenames()
    for path in sorted(RULES_DIR.glob("*.md")):
        text = path.read_text(encoding="utf-8")
        rel = path.relative_to(REPO_ROOT)
        for lineno, line in enumerate(text.splitlines(), start=1):
            for match in MD_TOKEN_RE.finditer(line):
                token = match.group(0)
                if "<" in line[max(0, match.start() - 1):match.start()]:
                    continue
                if token in PLACEHOLDER_TOKENS:
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
