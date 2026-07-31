# -*- coding: utf-8 -*-
"""
STDD test-file guard — an opt-in PreToolUse hook (only wired when the user
runs `install.sh --install-hook`).

Scope (STDD/spec.md REQ-09, specs/stdd-execute.md S-14): once Dispatch A
(builder-RED) establishes a RED fingerprint baseline for a test file, that
file SHALL NOT be written again before its owning task is marked `[x]` in
`tasks.md`. This hook enforces that ONE thing — it does NOT protect
frontmatter/`status`/fingerprint fields (REQ-09 explicitly excludes those;
see STDD/spec.md "REQ-09" and specs/stdd-spec.md S-05, which rely only on
user approval + `stdd-lint` after-the-fact comparison).

HEURISTIC / documented limitation: `specs/stdd-plan.md` S-07 mandates that
every TDD task in `tasks.md` names its exact test file and carries a
`[ ]`/`[wip]`/`[x]` status marker, but does not fix a literal line syntax
for either field. There is also no separate baseline-fingerprint file on
disk (the fingerprint is deliberately passed through the dispatch prompt
only, per S-14, so a builder can't tamper with a stored copy). So this
hook approximates "has an established RED baseline" as: the target file
path appears inside a backtick-quoted span in the same task block as a
`[wip]` marker, in any `STDD/*/tasks.md` under the current working
directory. If a project's tasks.md uses a different convention this
detector will under- or over-match — flagged here rather than silently
assumed correct.

Escape hatch for the one sanctioned exception (S-17 plan-drift recovery,
where Dispatch A is authorized to overwrite the same-named test file):
set TLOR_STDD_ALLOW_TEST_REWRITE=1 for that one recovery dispatch. The
mechanical layer cannot itself distinguish an authorized recovery rewrite
from an unauthorized one (per spec, it isn't required to) — a human
(the main session, per dispatch discipline) toggles this env var only for
the recovery call.

Fails open on any error — the guard must never break a session.

Honest limit (same class as scripts/stdd_custody_check.py's own disclosure):
`_same_file`'s dev+inode comparison (`os.path.samefile`) only fires when
BOTH the write target and the protected candidate already exist on disk at
check time. A HARD LINK created to a protected test file — a second path
whose inode is shared with the protected one — is only caught if that
second path itself already exists and is compared; a hard link created
fresh in the same PreToolUse turn that immediately targets a not-yet-seen
alias is not something this guard walks the filesystem to discover, and
there is no portable stdlib way to do so without that walk. Judged out of
proportion to the threat, same as the custody check's own hard-link note,
and deliberately not implemented here either.
"""
import json
import os
import re
import sys

STATUS_RE = re.compile(r"\[( |wip|x)\]")
BACKTICK_RE = re.compile(r"`([^`]+)`")
TEST_HINTS = ("test", "spec", "_test.", ".test.", "test_")

# Recognised change-directory layouts for tasks.md (REQ-19): the legacy
# STDD/<name>/ convention and the newer specs/<name>/ convention live side
# by side — see _find_tasks_md's docstring for the honest limit on both.
CHANGE_DIR_COMPONENTS = ("STDD", "specs")


def _is_probably_test_path(candidate):
    lowered = candidate.lower()
    return any(hint in lowered for hint in TEST_HINTS)


def _looks_like_a_path(candidate):
    """A backticked span only counts as a citation of the test FILE (REQ-09's
    scope) if it actually looks like a path — contains a `/` — and has no
    whitespace. This excludes bare test-function names (`test_login`) and
    verification commands (`pytest -q tests/test_foo.py`) from being
    collected as protected paths; both shapes contain a TEST_HINTS match but
    aren't a path citation."""
    if any(ch.isspace() for ch in candidate):
        return False
    return "/" in candidate


def _find_tasks_md(start_dir):
    """Find tasks.md files under any STDD/<name>/ or specs/<name>/ change
    directory below start_dir, per specs/stdd-plan.md S-07's fixed output
    path and REQ-19's specs/<name>/ layout.

    Honest limit (REQ-19): this walks the filesystem below start_dir looking
    for the literal directory components in CHANGE_DIR_COMPONENTS. It cannot
    know about a user-confirmed, non-repo change directory (REQ-18's `<dir>`
    branch, which need not be named specs/<name>) — only these two repo
    layouts are protected; any other layout is unprotected exactly as it was
    before this fix.
    """
    found = []
    for root, dirs, files in os.walk(start_dir):
        # skip hidden/vendor dirs to keep this cheap
        dirs[:] = [d for d in dirs if not d.startswith(".") and d not in ("node_modules", "vendor")]
        if "tasks.md" in files and any(c in root.split(os.sep) for c in CHANGE_DIR_COMPONENTS):
            found.append(os.path.join(root, "tasks.md"))
    return found


def _wip_protected_paths(tasks_md_path):
    """Return the set of test-file path fragments referenced inside any
    [wip]-marked task block of this tasks.md."""
    protected = set()
    try:
        with open(tasks_md_path, "r", encoding="utf-8") as fh:
            lines = fh.readlines()
    except OSError:
        return protected

    block = []
    block_is_wip = False

    def flush():
        if block_is_wip:
            for line in block:
                for m in BACKTICK_RE.finditer(line):
                    cand = m.group(1).strip()
                    # The framework's own tasks.md template (S-01/S-02)
                    # cites tests as `path/to/test_foo.py::test_name` — the
                    # `::test_name` suffix is a pytest node-id addressing
                    # the FUNCTION, not part of the file path, and must be
                    # stripped before the path check/comparison or a
                    # template-conformant citation can never equal the real
                    # file_path (which never carries that suffix).
                    path_part = cand.split("::", 1)[0]
                    if _is_probably_test_path(path_part) and _looks_like_a_path(path_part):
                        protected.add(path_part)

    for line in lines:
        m = STATUS_RE.search(line)
        if m and ("- [" in line or line.strip().startswith("[")):
            # a new task line starts here — flush the previous block first
            flush()
            block = [line]
            block_is_wip = m.group(1) == "wip"
        else:
            block.append(line)
    flush()
    return protected


def _resolve_under_root(path, root):
    """Normalize `path` (stripping `./`, collapsing `..`) and, if it's
    relative, resolve it against `root` — the same tree _find_tasks_md
    scanned. Then resolve any symlink components with `os.path.realpath`
    (root is expected to already be realpath'd by the caller). This is what
    lets a `./tests/test_foo.py` citation, or a path reached through a
    symlinked directory (macOS /tmp -> /private/tmp, a symlinked
    worktree/home, or an in-repo symlink alias), compare equal to the real,
    absolute file_path Claude Code passes in. `realpath` resolves symlinks
    in existing path components even when the final component doesn't
    exist yet, so a not-yet-created protected file is still handled."""
    normalized = os.path.normpath(path)
    if not os.path.isabs(normalized):
        normalized = os.path.normpath(os.path.join(root, normalized))
    return os.path.realpath(normalized)


def _same_file(file_path, candidate, root):
    """True only when file_path and candidate resolve to the exact same
    location under root, symlinks and case-folding included.

    This is a pure equality check on resolved absolute paths — no
    endswith-suffix matching. Suffix matching let a same-named file
    ANYWHERE below the tree (including entirely outside root) match,
    which is a cross-tree false-deny, not protection. Anchoring to root
    also means a file_path outside the tree this guard scanned is never
    considered protected, regardless of what candidate it happens to share
    a basename with.

    Both sides are realpath'd (see _resolve_under_root) so a symlinked
    directory component never defeats the comparison. When both resolved
    paths exist on disk, `os.path.samefile` (dev+inode) is used instead of
    a string compare, so a same-named file that differs only in case on a
    case-insensitive filesystem is still recognised as the same file. If
    either side doesn't exist yet (or the stat race-fails), fall back to a
    case-normalized string compare so a not-yet-created protected file is
    still covered.
    """
    norm_root = os.path.realpath(os.path.normpath(root))
    abs_file = _resolve_under_root(file_path, norm_root)
    abs_candidate = _resolve_under_root(candidate, norm_root)

    try:
        if os.path.commonpath([norm_root, abs_file]) != norm_root:
            return False
    except ValueError:
        # Mixed relative/absolute inputs or different drives/roots — the
        # guard's documented posture is fail-open on error, so this is
        # NOT protected rather than raising.
        return False

    if os.path.exists(abs_file) and os.path.exists(abs_candidate):
        try:
            return os.path.samefile(abs_file, abs_candidate)
        except OSError:
            pass

    return os.path.normcase(abs_file) == os.path.normcase(abs_candidate)


def is_protected_write(file_path, cwd):
    if not file_path:
        return False
    search_root = cwd or os.getcwd()
    for tasks_md in _find_tasks_md(search_root):
        for candidate in _wip_protected_paths(tasks_md):
            if _same_file(file_path, candidate, search_root):
                return True
    return False


def main():
    try:
        data = json.loads(sys.stdin.read() or "{}")
        tool_name = data.get("tool_name", "")
        tool_input = data.get("tool_input", {}) or {}
        cwd = data.get("cwd", "")

        if tool_name not in ("Edit", "Write", "NotebookEdit"):
            return 0

        if os.environ.get("TLOR_STDD_ALLOW_TEST_REWRITE") == "1":
            return 0

        file_path = tool_input.get("file_path", "") or tool_input.get("notebook_path", "")
        if not is_protected_write(file_path, cwd):
            return 0

        print(json.dumps({
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": (
                    "STDD test-file guard: this test file has an established "
                    "RED fingerprint baseline ([wip] task in tasks.md) — "
                    "further writes are blocked until the task is marked "
                    "[x] (REQ-09 / specs/stdd-execute.md S-14). The only "
                    "sanctioned exception is the S-17 plan-drift recovery "
                    "rewrite by Dispatch A; for that one call set "
                    "TLOR_STDD_ALLOW_TEST_REWRITE=1."
                ),
            }
        }, ensure_ascii=False))
    except Exception:
        pass  # fail-open: guard failure must never block a session
    return 0


if __name__ == "__main__":
    sys.exit(main())
