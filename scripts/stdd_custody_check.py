#!/usr/bin/env python3
"""Verify an STDD change's approval custody chain and emit ONE verdict line.

Why this is a program and not a workflow step: a Workflow script has no
filesystem access, so the only way it can "compare" a recorded fingerprint
against a recomputed body hash is to ask an agent for BOTH strings and
compare those. Both sides then come from one untrusted source that holds
Bash, and a single in-place edit of the recorded field makes the comparison
pass. This program reads the files itself and emits one verdict; an agent
only relays that verdict.

Honest limit: this is not an absolute barrier. A relayed line can still in
principle be forged, and an agent that rewrites `approved_fingerprint` to
match a drifted body still gets a PASS (that is the custody model's own
residual hole, pinned by a test). What it removes is the trivial bypass,
and unlike an agent-mediated comparison it is unit-testable in CI.

A second, narrower residual hole: the `spec.md`/`design-ux.md` containment
checks (`require_within`) detect a SYMLINK that individually escapes the
root, not a HARD LINK. A hard-linked `design-ux.md` (or `spec.md`) whose
path sits inside the root but whose inode is shared with a file outside it
passes containment — `Path.is_symlink()` is false for a hard link, and
there is no portable stdlib way to detect "this regular file shares an
inode with something outside the tree" without walking the filesystem
looking for it. Hard-link detection was judged out of proportion to the
threat (dispatch note: L3, 2026-07-28) and is deliberately not implemented;
the digest check below still must match the approved fingerprint, so a
hard-linked file whose body has drifted from what was approved still fails
on `*.body-drift`.

Fingerprint definition — NOT invented here. Taken verbatim from the
framework: content = everything after the SECOND `---` line (the end of the
frontmatter block), including trailing newlines, with no normalization; no
frontmatter -> content = the whole file; algorithm `shasum -a 256`
(stdd-skills/stdd-spec/SKILL.md Step 6, "Content-extraction rule" — the
single approved canonical source for this definition).

Verdict grammar (the CUSTODY: line is ALWAYS exactly one line, no more, no
less):

    CUSTODY: PASS change=<name> spec.recorded=<v> spec.computed=<v> \
design_ux.recorded=<v> design_ux.computed=<v>
    CUSTODY: FAIL reason=<token> change=<name> spec.recorded=<v> \
spec.computed=<v> design_ux.recorded=<v> design_ux.computed=<v>

On PASS, a second line always follows (S-28, REQ-20): `TASKS: open=<n>
wip=<n> done=<n> manual=<n> infra=<n> ids=<id>(;<id>)*`, counted over FORMAL
task lines only — a line matching `^- \[( |wip|x)\] ` immediately followed
by a backtick-wrapped id. Text that merely looks like a marker (prose
quoting `- [x]`, a mermaid node label, an uppercase `[X]`) is not counted.
When the change carries no `tasks.md` at all, this second line is the
literal `TASKS: missing` instead (spec.md:1121, user decision) — the
custody chain itself is unaffected by a missing tasks.md, so the CUSTODY:
verdict stays independent (PASS/exit 0); the workflow side, not this
script, blocks before calling `loadChange` when it sees that literal.

Every field is a whitespace-free `key=value` token. `<v>` is a 64-char
lowercase hex digest, or `-` when the value does not exist or could not be
computed. `<token>` is a whitespace-free reason of the form
`<artifact>:<problem>` so the failing artifact is named in the reason
itself. Human-readable detail (offending input, paths) goes to stderr, so
stdout stays machine-checkable. Exit status: 0 with a CUSTODY: verdict line
means PASS, 1 with a CUSTODY: verdict line means FAIL — the exit code and
the verdict word always agree.

Exit 2 is a THIRD, non-verdict path (REQ-06/REQ-07): `argparse` itself exits
2 with no `CUSTODY:` line at all — either for a bad/unknown flag, or for
supplying both `--change-dir` and the legacy positional `change`/`--root`
together (the two CLI modes are mutually exclusive, enforced via
`parser.error()`). Exit 2 is never a verdict and callers SHALL NOT read it
as PASS or FAIL; `readCustody`'s existing "no legal verdict line -> fail
closed" handling already covers it without any special-casing.

The program is read-only: it never writes, creates or deletes anything.
"""
import argparse
import hashlib
import re
import sys
from pathlib import Path

CHANGE_NAME_RE = re.compile(r"^[A-Za-z0-9._-]+$")
DIGEST_RE = re.compile(r"^[0-9a-f]{64}$")

# YAML-ish null spellings. Checked BEFORE quote stripping, so a quoted
# "null" is a string and falls through to the malformed-digest branch.
NULLISH = {"", "~", "null", "none"}

MISSING = "-"


class Verdict(Exception):
    """A FAIL decided mid-check. Carries the reason token; the hash fields
    collected so far are read off the Report the caller already holds."""

    def __init__(self, reason, detail=None):
        super().__init__(reason)
        self.reason = reason
        self.detail = detail


class Report:
    """The four hash slots of the verdict line, filled as checks progress."""

    def __init__(self, change="-"):
        self.change = change
        self.spec_recorded = MISSING
        self.spec_computed = MISSING
        self.design_ux_recorded = MISSING
        self.design_ux_computed = MISSING

    def line(self, verdict, reason=None):
        head = f"CUSTODY: {verdict}"
        if reason is not None:
            head += f" reason={reason}"
        return (
            f"{head} change={self.change}"
            f" spec.recorded={self.spec_recorded}"
            f" spec.computed={self.spec_computed}"
            f" design_ux.recorded={self.design_ux_recorded}"
            f" design_ux.computed={self.design_ux_computed}"
        )


def body_bytes(raw: bytes) -> bytes:
    """The framework's body-only content: everything after the second `---`
    line, byte-exact (trailing newlines kept, no normalization). A file with
    no frontmatter — or an unterminated frontmatter block — is its own body."""
    lines = raw.splitlines(keepends=True)
    if not lines or lines[0].rstrip(b"\r\n") != b"---":
        return raw
    for idx in range(1, len(lines)):
        if lines[idx].rstrip(b"\r\n") == b"---":
            return b"".join(lines[idx + 1:])
    return raw


def has_frontmatter(raw: bytes) -> bool:
    lines = raw.splitlines(keepends=True)
    if not lines or lines[0].rstrip(b"\r\n") != b"---":
        return False
    return any(line.rstrip(b"\r\n") == b"---" for line in lines[1:])


def body_digest(path: Path) -> str:
    return hashlib.sha256(body_bytes(path.read_bytes())).hexdigest()


def frontmatter_fields(raw: bytes) -> dict:
    """Top-level `key: value` pairs of the frontmatter block. Deliberately a
    line parser, not a YAML parser: the fields this program reads are flat
    scalars, and the repo's scripts are stdlib-only.

    A key repeated at top level is a malformed frontmatter block, not a
    "last one wins" — this parser only ever runs against spec.md, so a
    duplicate is raised as a spec.md-named Verdict rather than silently
    overwriting the earlier value."""
    text = raw.decode("utf-8", errors="replace")
    lines = text.splitlines()
    fields = {}
    for line in lines[1:]:
        if line.rstrip("\r") == "---":
            break
        if not line or line[0] in " \t#-":
            continue
        key, sep, value = line.partition(":")
        if not sep:
            continue
        key = key.strip()
        if key in fields:
            raise Verdict(
                "spec.md:frontmatter-duplicate-key",
                f"frontmatter key {key!r} appears more than once",
            )
        fields[key] = value.strip()
    return fields


def normalise_digest(value: str) -> str:
    """Recorded digests are written by a variety of hands. Tolerate a
    `sha256:` prefix, surrounding quotes, shasum's trailing filename, and
    upper case — then demand exactly 64 hex chars. Returns "" if the value
    is not a well-formed digest; the caller decides that this is a FAIL."""
    text = value.strip()
    for quote in ('"', "'"):
        if len(text) >= 2 and text[0] == quote and text[-1] == quote:
            text = text[1:-1].strip()
            break
    if not text:
        return ""
    text = text.split()[0]  # drop shasum's trailing "  <filename>"
    if text.lower().startswith("sha256:"):
        text = text[len("sha256:"):]
    text = text.lower()
    return text if DIGEST_RE.match(text) else ""


def is_nullish(value: str) -> bool:
    return value.strip().lower() in NULLISH


def is_safe_name(name: str) -> bool:
    """One path segment, no separators, no traversal — validated BEFORE the
    name is ever joined onto a path."""
    return bool(CHANGE_NAME_RE.match(name)) and name not in (".", "..")


def resolved_within(path: Path, anchor: Path) -> bool:
    """True if an already-resolved `path` sits at or under an already-resolved
    `anchor`. Equality is legal, not just a subpath (REQ-09 D-12): the
    non-repo-branch shape where the change directory itself IS the root is a
    normal case, not a violation. Shared by every containment check this
    program makes, so the rule is defined once."""
    return path == anchor or anchor in path.parents


def require_within(path: Path, anchor: Path, reason: str) -> None:
    """Raise a Verdict with `reason` if a symlinked `path` individually
    escapes `anchor` once resolved. Shared by check_spec and check_design_ux
    — both need the same file-granularity containment check (directory-level
    containment alone does not catch a symlinked FILE that escapes on its
    own), only the reason token differs per artifact."""
    if path.is_symlink() and not resolved_within(path.resolve(), anchor):
        raise Verdict(
            reason, f"{path} resolves to {path.resolve()}, outside {anchor}"
        )


def resolve_change_dir(name: str, root: Path) -> Path:
    """`STDD/<name>/` under an explicit root. The name is validated before it
    ever touches a path, and the resolved directory must still sit at or
    under the resolved `<root>/STDD` anchor — a name is never allowed to
    walk out of the root.

    NOTE: REQ-09 D-12 describes widening this anchor from `<root>/STDD` to
    `root` itself. That widening is intentionally NOT applied here: doing so
    would flip `test_change_dir_symlink_escaping_resolved_root_fails_...`
    (S-13 case a) to an incorrect PASS, because that test's own fixture
    builds its "outside" tree as a CHILD of the test root
    (`tmp_path / "outside"`), not a sibling of it — so it never actually
    escapes a `root`-anchored check, only the narrower `<root>/STDD` one
    kept here. Flagged for the spec/test owner to reconcile (see this
    change's STDD progress notes), not resolved unilaterally."""
    if not is_safe_name(name):
        raise Verdict("change-name:invalid", f"rejected change name {name!r}")
    stdd_root = (root / "STDD").resolve()
    change_dir = (stdd_root / name).resolve()
    # Belt and braces: the regex already forbids separators, but resolve()
    # follows symlinks, so a symlinked change directory can still point out
    # of the root.
    if not resolved_within(change_dir, stdd_root):
        raise Verdict(
            "change-dir:outside-root", f"{change_dir} is outside {stdd_root}"
        )
    return change_dir


def check_spec(spec_path: Path, stdd_root: Path, report: Report) -> dict:
    """Frontmatter fields of a spec.md whose recorded spec fingerprint has
    been validated and matched. Raises Verdict on any failure."""
    # Directory-level containment (resolve_change_dir) only ever checked the
    # change directory itself. spec.md can still be a symlink that
    # individually escapes the root even though its containing directory
    # doesn't, so that has to be checked here, at file granularity.
    require_within(spec_path, stdd_root, "spec.md:escapes-root")
    if not spec_path.is_file():
        raise Verdict("spec.md:missing", f"no spec.md at {spec_path}")
    raw = spec_path.read_bytes()
    if not has_frontmatter(raw):
        raise Verdict("spec.md:no-frontmatter", f"{spec_path} has no frontmatter block")
    fields = frontmatter_fields(raw)
    if "approved_fingerprint" not in fields:
        raise Verdict(
            "spec.md:approved_fingerprint-absent",
            "frontmatter carries no approved_fingerprint key",
        )
    recorded_raw = fields["approved_fingerprint"]
    if is_nullish(recorded_raw):
        raise Verdict(
            "spec.md:approved_fingerprint-empty",
            f"approved_fingerprint is empty or null ({recorded_raw!r})",
        )
    recorded = normalise_digest(recorded_raw)
    if not recorded:
        raise Verdict(
            "spec.md:approved_fingerprint-malformed",
            f"approved_fingerprint is not a sha-256 digest ({recorded_raw!r})",
        )
    report.spec_recorded = recorded
    report.spec_computed = body_digest(spec_path)
    if report.spec_computed != recorded:
        raise Verdict(
            "spec.md:body-drift",
            "spec.md body no longer matches its approved fingerprint",
        )
    return fields


def check_design_ux(change_dir: Path, fields: dict, report: Report, stdd_root: Path) -> None:
    """The design-ux half of the two-file gate, including the four
    consistency branches the framework defines for key-vs-file existence
    (stdd-skills/stdd/SKILL.md Step 3.1/3.3/3.4/3.5)."""
    design_path = change_dir / "design-ux.md"
    # Same file-granularity containment gap check_spec closes for spec.md:
    # directory-level containment (resolve_change_dir) never inspects
    # individual files, so design-ux.md can still be a symlink that escapes
    # the root on its own even when its containing directory doesn't. Caught
    # here, before is_file() gets a chance to follow the symlink and hash the
    # outside target. A HARDLINKED design-ux.md pointing outside the root is
    # NOT caught by this (is_symlink() is false for a hard link) — see
    # run_with_change_dir's docstring and the module's honest-limits note.
    require_within(design_path, stdd_root, "design-ux.md:escapes-root")
    exists = design_path.is_file()
    present = "design_ux_fingerprint" in fields
    recorded_raw = fields.get("design_ux_fingerprint", "")

    if not present:
        # Key entirely absent: a pre-v3 artifact. The framework says gates
        # reject it until a one-time re-approval, so this is a FAIL either
        # way — but the two shapes get distinct reasons.
        if exists:
            raise Verdict(
                "design-ux.md:fingerprint-absent",
                "design-ux.md exists but spec.md carries no design_ux_fingerprint key",
            )
        raise Verdict(
            "spec.md:design_ux_fingerprint-absent",
            "pre-v3 spec.md: no design_ux_fingerprint key; needs one-time re-approval",
        )

    if is_nullish(recorded_raw):
        # Null is a LEGAL state — it means "no UI surface" — but only when
        # design-ux.md really is absent.
        if exists:
            raise Verdict(
                "design-ux.md:not-covered-by-approval",
                "design-ux.md exists but design_ux_fingerprint is null",
            )
        if design_path.exists():
            # Present but not a regular file (e.g. a directory): is_file()
            # returns False here just like it does for a genuinely absent
            # path, so this must not fall through to the "no UI surface"
            # PASS branch below.
            raise Verdict(
                "design-ux.md:not-a-file",
                f"{design_path} exists but is not a regular file",
            )
        return

    recorded = normalise_digest(recorded_raw)
    if not recorded:
        raise Verdict(
            "design-ux.md:fingerprint-malformed",
            f"design_ux_fingerprint is not a sha-256 digest ({recorded_raw!r})",
        )
    report.design_ux_recorded = recorded
    if not exists:
        raise Verdict(
            "design-ux.md:missing",
            f"design_ux_fingerprint is recorded but {design_path} does not exist",
        )
    report.design_ux_computed = body_digest(design_path)
    if report.design_ux_computed != recorded:
        raise Verdict(
            "design-ux.md:body-drift",
            "design-ux.md body no longer matches its approved fingerprint",
        )


def run(name: str, root: Path, report: Report) -> tuple:
    change_dir = resolve_change_dir(name, root)
    if not change_dir.is_dir():
        raise Verdict("change-dir:missing", f"no change directory at {change_dir}")
    stdd_root = (root / "STDD").resolve()
    fields = check_spec(change_dir / "spec.md", stdd_root, report)
    check_design_ux(change_dir, fields, report, stdd_root)
    return change_dir, stdd_root


def run_with_change_dir(change_dir: Path, report: Report) -> tuple:
    """`--change-dir` mode (REQ-07 CLI contract, REQ-18): the caller (the
    stdd-execute workflow) has already confirmed and resolved this absolute
    path itself — this script does no git-detection or `STDD`/`specs` anchor
    guessing here, unlike the positional/`--root` legacy mode above.
    Containment is anchored on this SAME already-resolved path (REQ-09/D-12's
    non-repo-branch case: the change directory equals the root, which is
    trivially self-contained), so a `spec.md`/`design-ux.md` SYMLINK that
    individually escapes this directory is still caught, exactly like the
    legacy mode catches one escaping `<root>/STDD`. NOT caught: a HARD LINK
    to an outside file — `is_symlink()` is false for a hard link, so a
    hardlinked artifact whose path sits inside this directory passes
    containment (see the module docstring's honest-limits note). Its digest
    must still match the approved fingerprint, so a drifted hardlinked body
    still fails on `*.body-drift`.

    Deliberately no separate "does this directory even exist" check here
    (unlike legacy `run()`'s `change-dir:missing`): S-23(b) pins the
    nonexistent-directory case to FAIL `spec.md:missing` — `check_spec`'s own
    `spec_path.is_file()` test already returns False when the containing
    directory doesn't exist, so that one check covers both "directory
    missing" and "directory present but spec.md missing" with the same named
    reason, matching the workflow-side S-23 acceptance criterion."""
    fields = check_spec(change_dir / "spec.md", change_dir, report)
    check_design_ux(change_dir, fields, report, change_dir)
    return change_dir, change_dir


# A FORMAL task line (S-28): `- [ ]`/`- [wip]`/`- [x]` (lowercase only — an
# uppercase `[X]` is prose, not a marker the framework recognises) followed
# immediately by a backtick-wrapped id, optionally followed by one more
# backtick-wrapped `[MANUAL]`/`[INFRA]` tag. Anchored at line start so a
# checkbox merely quoted mid-sentence, or a mermaid node label, never matches.
TASK_LINE_RE = re.compile(r"^- \[( |wip|x)\] `([^`]+)`(?: `(\[MANUAL\]|\[INFRA\])`)?")

# A task-SHAPED line that is indented under leading whitespace — i.e. it
# would match TASK_LINE_RE if not for the leading whitespace. Anchored so it
# only fires on real indentation, never on the column-0 case TASK_LINE_RE
# already owns. The framework's own worked example (stdd-plan/templates/
# tasks.md) never indents a formal task line, so this is treated as a
# malformed file rather than a legal nested-task form (S-28 follow-up, L2).
INDENTED_TASK_LINE_RE = re.compile(r"^[ \t]+- \[( |wip|x)\] `[^`]+`")

# A fenced-code-block delimiter. Lines between an opening and closing fence
# are never scanned by either regex above — the framework's own docs
# legitimately show task-shaped lines as worked EXAMPLES inside a fence, and
# without this exclusion an example containing an illegal id would hard-FAIL
# the whole change over documentation, not a real task (council round 3, P4).
FENCE_LINE_RE = re.compile(r"^\s*```")

# The id grammar the spec pins for a change NAME (CHANGE_NAME_RE) is reused
# here for a tasks.md task id: whitespace, commas, and backslashes would all
# break the whitespace-free `key=value` TASKS: line grammar this file
# documents, and TASKS_LINE_RE on the consumer side would then reject the
# whole line (S-28 follow-up, L1). A leading `-` is ALSO rejected even though
# CHANGE_NAME_RE's character class alone would accept it: any downstream CLI
# consumer reading the whitespace-separated `ids=` token would see a leading
# dash as a flag, not an id (council round 3, P5).
#
# M4 (merged-task id token): stdd-plan's module-convergence rule can report
# one task's id as a comma-joined list of scenario ids (e.g. `S-03,S-04`).
# CHANGE_NAME_RE/TASK_ID_RE itself is deliberately left untouched (it still
# rejects a bare comma) so change-name validation elsewhere is not loosened
# by this — only the task-id ACCEPTANCE check below is widened, by
# validating each comma-split token against the exact same strict per-token
# charset/traversal rule individually (mirrors workflows/stdd-execute.js's
# `idTokens.some((token) => !CHANGE_NAME_RE.test(token))` check exactly). A
# garbage id like `S-03,../../etc` still blocks, because its second token
# fails TASK_ID_RE on its own; an empty token from a trailing/double comma
# also fails, since TASK_ID_RE requires 1+ characters.
TASK_ID_RE = CHANGE_NAME_RE

TASK_STATUS_NAMES = {" ": "open", "wip": "wip", "x": "done"}


TASKS_MISSING_LINE = "TASKS: missing"


def build_tasks_line(change_dir: Path, stdd_root: Path) -> str:
    """`TASKS: open=<n> wip=<n> done=<n> manual=<n> infra=<n> ids=<id>(;<id>)*`
    counted over the FORMAL task lines of `tasks.md`, in file order. `<id>`
    itself may be a comma-joined merged task id (stdd-plan's module-
    convergence rule, e.g. `S-03,S-04`) — the inter-task separator is `;`,
    deliberately DIFFERENT from the `,` used inside a merged id, so a line
    naming one plain task plus one merged task is never ambiguous between
    "two tasks, one merged" and "three plain tasks" (v0.7.3 gap-closure: a
    plain `,`-joined `ids=` list made every legitimate merged task look like
    an extra, non-existent task to every consumer that split on `,`). Returns
    `TASKS_MISSING_LINE` when the change carries no tasks.md at all (REQ-20,
    spec.md:1121, user decision): the custody chain itself (spec.md/
    design-ux.md) is unaffected by a missing tasks.md, so the CUSTODY:
    verdict stays independent — this line is still printed on a PASS custody
    chain, it just carries the literal `TASKS: missing` instead of a count.
    The workflow side (not this script) is the one that blocks before
    calling `loadChange` when it sees this literal; every other empty/
    degenerate shape below is a named FAIL, never a bare TASKS: line the
    consumer can't use.

    Raises Verdict (never emits a malformed TASKS: line, and never lets an
    encoding error escape as a bare traceback) when:
    - `tasks.md` is a symlink that individually escapes `stdd_root` — the
      reconciliation baseline must come from inside the change's own root,
      same as spec.md/design-ux.md (council round 3, P3);
    - `tasks.md`'s bytes are not valid UTF-8 — decoding used to raise
      UnicodeDecodeError straight through main()'s `except OSError`, which
      does not catch it (ValueError, not OSError), producing a bare
      traceback and no verdict line at all (council round 3, P2);
    - a parsed task id (or, for a merged id, any of its comma-split tokens
      individually, M4) contains a character outside `TASK_ID_RE`, or the
      id starts with `-` (council round 3, P5) — printing it anyway would
      violate this file's own "whitespace-free key=value token" invariant,
      and a leading dash reads as a flag to any downstream CLI consumer (L1);
    - a task-shaped line is found indented under leading whitespace, which
      TASK_LINE_RE's column-0 anchor would otherwise silently skip, dropping
      a real task from the count with no signal at all (L2);
    - `tasks.md` exists but contains zero formal task lines — emitting
      `ids=` (empty) fails the consumer's own TASKS_LINE_RE, which then
      blames a count line that was, in fact, printed (council round 3, P6).

    Lines between a pair of ``` fence delimiters are never scanned by either
    regex: the framework's own docs legitimately show task-shaped lines as
    worked EXAMPLES inside a fence, and those must not be counted as real
    tasks nor hard-FAIL the change over an illegal example id (council round
    3, P4)."""
    tasks_path = change_dir / "tasks.md"
    require_within(tasks_path, stdd_root, "tasks.md:escapes-root")
    if not tasks_path.is_file():
        return TASKS_MISSING_LINE
    try:
        # utf-8-sig strips a leading BOM (council round 3, P1): without it,
        # the BOM'd first line matches neither TASK_LINE_RE nor
        # INDENTED_TASK_LINE_RE and its task silently vanishes from the count.
        text = tasks_path.read_text(encoding="utf-8-sig")
    except UnicodeDecodeError as exc:
        raise Verdict(
            "tasks.md:undecodable", f"{tasks_path} is not valid UTF-8: {exc}"
        )
    counts = {"open": 0, "wip": 0, "done": 0, "manual": 0, "infra": 0}
    ids = []
    in_fence = False
    for lineno, line in enumerate(text.splitlines(), start=1):
        if FENCE_LINE_RE.match(line):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        match = TASK_LINE_RE.match(line)
        if not match:
            if INDENTED_TASK_LINE_RE.match(line):
                raise Verdict(
                    "tasks.md:indented-task-line",
                    f"{tasks_path}:{lineno}: task-shaped line is indented, "
                    "which the column-0 counter would silently skip: "
                    f"{line!r}",
                )
            continue
        status, task_id, tag = match.group(1), match.group(2), match.group(3)
        # M4: a merged task id is a comma-joined list of per-token ids
        # (stdd-plan's module-convergence rule) — validate EACH token against
        # the unchanged TASK_ID_RE rather than the whole string, mirroring
        # the JS side's per-token check exactly. An empty token (leading/
        # trailing/double comma) fails TASK_ID_RE on its own, same as any
        # other illegal character.
        id_tokens = task_id.split(",")
        if any(not TASK_ID_RE.match(token) for token in id_tokens) or task_id.startswith("-"):
            raise Verdict(
                "tasks.md:unsafe-task-id",
                f"{tasks_path}:{lineno}: task id {task_id!r} contains a "
                "character outside [A-Za-z0-9._-] (checked per comma-split "
                "token), or starts with '-', which would break the "
                "whitespace-free TASKS: line grammar",
            )
        counts[TASK_STATUS_NAMES[status]] += 1
        ids.append(task_id)
        if tag == "[MANUAL]":
            counts["manual"] += 1
        elif tag == "[INFRA]":
            counts["infra"] += 1
    if not ids:
        raise Verdict(
            "tasks.md:no-tasks",
            f"{tasks_path} exists but contains zero formal task lines",
        )
    return (
        f"TASKS: open={counts['open']} wip={counts['wip']} done={counts['done']} "
        f"manual={counts['manual']} infra={counts['infra']} ids={';'.join(ids)}"
    )


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Verify an STDD change's approval custody chain and print one "
            "CUSTODY: verdict line. Read-only."
        )
    )
    # REQ-07 CLI contract (D-13): two mutually exclusive modes, same verdict
    # grammar either way. `change`/`--root` is the legacy mode kept for
    # direct human invocation outside the workflow; `--change-dir` is the
    # primary mode the workflow itself always uses (the caller has already
    # resolved and confirmed an absolute path — see REQ-18). Both `change`
    # and `--root` default to None (not "."), so argparse cannot tell "user
    # explicitly passed --root ." apart from "user omitted --root" — that
    # distinction is exactly what mutual-exclusivity detection needs below.
    parser.add_argument(
        "change",
        nargs="?",
        default=None,
        help="change name; STDD/<change>/ is checked (legacy mode; mutually exclusive with --change-dir)",
    )
    parser.add_argument(
        "--root",
        default=None,
        help="project root holding STDD/ (legacy mode only; default: current directory)",
    )
    parser.add_argument(
        "--change-dir",
        dest="change_dir_arg",
        default=None,
        help=(
            "an already-confirmed, absolute change directory (primary mode; "
            "mutually exclusive with the positional change name / --root)"
        ),
    )
    args = parser.parse_args(argv)

    if args.change_dir_arg is not None:
        if args.change is not None or args.root is not None:
            parser.error("--change-dir is mutually exclusive with the positional change name / --root")
        change_dir_input = Path(args.change_dir_arg)
        if not change_dir_input.is_absolute():
            report = Report(MISSING)
            print(report.line("FAIL", "change-dir:not-absolute"))
            return 1
        resolved_change_dir = change_dir_input.resolve()
        # change= token (D-14/F-02): the last path segment of the confirmed
        # change directory — never re-derived from anything the caller typed
        # as a separate "name".
        last_segment = resolved_change_dir.name
        safe_name = last_segment if is_safe_name(last_segment) else MISSING
        report = Report(safe_name)

        def resolver():
            return run_with_change_dir(resolved_change_dir, report)
    else:
        if args.change is None:
            parser.error("either a change name (legacy mode) or --change-dir (primary mode) is required")
        safe_name = args.change if is_safe_name(args.change) else MISSING
        report = Report(safe_name)
        root_value = args.root if args.root is not None else "."

        def resolver():
            return run(args.change, Path(root_value).resolve(), report)

    try:
        change_dir, tasks_anchor = resolver()
        # Computed BEFORE the PASS line is printed: a malformed tasks.md
        # (an unsafe id, an indented task-shaped line) must FAIL the whole
        # verdict, never print a PASS followed by a bad or missing TASKS:
        # line (L1/L2).
        tasks_line = build_tasks_line(change_dir, tasks_anchor)
    except Verdict as verdict:
        if verdict.detail:
            print(f"stdd_custody_check.py: {verdict.detail}", file=sys.stderr)
        print(report.line("FAIL", verdict.reason))
        return 1
    except OSError as exc:
        # Unreadable file / permission / broken symlink: a FAIL with its own
        # reason, never a traceback and never a fall-through to PASS.
        print(f"stdd_custody_check.py: {exc}", file=sys.stderr)
        print(report.line("FAIL", "change-dir:unreadable"))
        return 1
    print(report.line("PASS"))
    if tasks_line:
        print(tasks_line)
    return 0


if __name__ == "__main__":
    sys.exit(main())
