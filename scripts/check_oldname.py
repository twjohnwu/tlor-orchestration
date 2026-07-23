#!/usr/bin/env python3
"""Guard against unbounded old-name (`tlor-agents`) residue.

Stdlib only. The repo was renamed tlor-agents -> tlor-orchestration; a
handful of historical mentions in the changelog/history docs are expected
and capped. Any occurrence outside the whitelist, or a whitelisted file
exceeding its cap, fails the check.
"""
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
OLD_NAME = "tlor-agents"
SELF_PATH = Path(__file__).resolve()
SELF_REL = SELF_PATH.relative_to(REPO_ROOT).as_posix()

# path (repo-relative, posix style) -> max allowed occurrence count
WHITELIST = {
    "docs/release_log.md": 2,
    "docs/en/history.md": 3,
    "docs/zh-TW/history.md": 3,
}


def iter_repo_files():
    """Yield repo-content files: git-tracked plus untracked-but-not-ignored.

    Deliberately excludes gitignored paths (local scratch, backups) — those
    never ship in the published repo or a CI checkout, so old-name residue
    there is out of scope for this guard. Falls back to a plain filesystem
    walk (excluding .git) if git is unavailable.
    """
    try:
        out = subprocess.run(
            ["git", "ls-files", "--cached", "--others", "--exclude-standard"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=True,
        ).stdout
        for rel in out.splitlines():
            path = REPO_ROOT / rel
            if path.is_file():
                yield path
        return
    except (subprocess.CalledProcessError, FileNotFoundError):
        pass

    for path in REPO_ROOT.rglob("*"):
        if not path.is_file():
            continue
        if ".git" in path.relative_to(REPO_ROOT).parts:
            continue
        yield path


def main() -> int:
    errors = []
    for path in iter_repo_files():
        rel = path.relative_to(REPO_ROOT).as_posix()
        if rel == SELF_REL:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        count = text.count(OLD_NAME)
        if count == 0:
            continue
        cap = WHITELIST.get(rel)
        if cap is None:
            errors.append(f"{rel}: {count} occurrence(s) — not whitelisted")
        elif count > cap:
            errors.append(f"{rel}: {count} occurrence(s) — exceeds cap of {cap}")

    if errors:
        print(f"check_oldname.py: {len(errors)} violation(s):")
        for err in errors:
            print(f"  - {err}")
        return 1

    print("check_oldname.py: OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
