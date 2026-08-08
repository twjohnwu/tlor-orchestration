# -*- coding: utf-8 -*-
"""Black-box tests for scripts/stdd_custody_check.py.

Same style as the hook and erebor tests: the script is invoked as a
subprocess exactly as a caller would invoke it, and only its stdout verdict
line and exit status are asserted against — no internals are imported.
Every fixture STDD tree is SYNTHETIC and built under pytest's tmp_path and
handed to the script via `--root`; no real `STDD/` tree and no home
directory is ever read.
"""
import hashlib
import os
import re
import subprocess
import sys

import pytest

from conftest import REPO_ROOT

SCRIPT = REPO_ROOT / "scripts" / "stdd_custody_check.py"

SPEC_BODY = """\
# Some change

## S-01 Something happens

GIVEN a thing
WHEN it is poked
THEN it responds
"""

DESIGN_BODY = """\
# Design

A layout description.
"""


# --------------------------------------------------------------------------
# Fixture builders
# --------------------------------------------------------------------------

def body_fingerprint(body: str) -> str:
    """The framework's body-only digest: everything after the second `---`
    line, byte-exact. Computed here independently of the script."""
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


def spec_text(fingerprint, design_fingerprint=None, body=SPEC_BODY, frontmatter=True):
    """A spec.md. `fingerprint`/`design_fingerprint` are written verbatim, so
    a test can plant a malformed or oddly-quoted value; None omits the key."""
    if not frontmatter:
        return body
    lines = ["---", "status: approved", "approved_date: 2026-01-01"]
    if fingerprint is not None:
        lines.append(f"approved_fingerprint: {fingerprint}")
    if design_fingerprint is not None:
        lines.append(f"design_ux_fingerprint: {design_fingerprint}")
    lines.append("---")
    return "\n".join(lines) + "\n" + body


def make_change(tmp_path, name="some-change", spec=None, design=None):
    """Build STDD/<name>/ under tmp_path. Returns the change directory."""
    change_dir = tmp_path / "STDD" / name
    change_dir.mkdir(parents=True)
    if spec is not None:
        (change_dir / "spec.md").write_text(spec, encoding="utf-8")
    if design is not None:
        (change_dir / "design-ux.md").write_text(design, encoding="utf-8")
    return change_dir


def make_valid_change(tmp_path, name="some-change", spec_body=SPEC_BODY, design_body=None):
    """The happy path: a change whose recorded fingerprints match its bodies."""
    design_fp = body_fingerprint(design_body) if design_body is not None else "null"
    spec = spec_text(body_fingerprint(spec_body), design_fp, body=spec_body)
    return make_change(tmp_path, name, spec=spec, design=design_body)


def run_check(tmp_path, name="some-change", root=None):
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), name, "--root", str(root or tmp_path)],
        capture_output=True,
        text=True,
    )
    return proc


def verdict_fields(stdout):
    """Parse the CUSTODY: verdict into (word, {key: value}) — the FIRST
    stdout line only. It used to assert stdout was exactly one line, but
    REQ-20 now always follows a PASS with a second line (a TASKS: count or
    the literal `TASKS: missing`), so this only ever looks at line one; any
    test that cares about the second line reads `stdout.splitlines()`
    itself."""
    lines = stdout.splitlines()
    assert lines, "expected at least one stdout line"
    line = lines[0]
    assert line.startswith("CUSTODY: "), line
    tokens = line[len("CUSTODY: "):].split()
    fields = dict(token.split("=", 1) for token in tokens[1:])
    return tokens[0], fields


# --------------------------------------------------------------------------
# Happy path
# --------------------------------------------------------------------------

def test_matching_fingerprint_passes(tmp_path):
    make_valid_change(tmp_path)
    proc = run_check(tmp_path)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    word, fields = verdict_fields(proc.stdout)
    assert word == "PASS"
    assert fields["change"] == "some-change"
    assert fields["spec.recorded"] == fields["spec.computed"] == body_fingerprint(SPEC_BODY)


def test_matching_two_file_fingerprint_passes(tmp_path):
    make_valid_change(tmp_path, design_body=DESIGN_BODY)
    proc = run_check(tmp_path)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    word, fields = verdict_fields(proc.stdout)
    assert word == "PASS"
    assert fields["design_ux.recorded"] == fields["design_ux.computed"] == body_fingerprint(DESIGN_BODY)


def test_verdict_line_carries_all_four_hash_fields(tmp_path):
    make_valid_change(tmp_path)
    proc = run_check(tmp_path)
    _, fields = verdict_fields(proc.stdout)
    assert set(fields) == {
        "change",
        "spec.recorded",
        "spec.computed",
        "design_ux.recorded",
        "design_ux.computed",
    }


# --------------------------------------------------------------------------
# Drift
# --------------------------------------------------------------------------

def test_spec_body_drift_fails_and_names_spec_md(tmp_path):
    change_dir = make_valid_change(tmp_path)
    (change_dir / "spec.md").write_text(
        spec_text(body_fingerprint(SPEC_BODY), "null", body=SPEC_BODY + "x"),
        encoding="utf-8",
    )
    proc = run_check(tmp_path)
    assert proc.returncode != 0
    word, fields = verdict_fields(proc.stdout)
    assert word == "FAIL"
    assert fields["reason"] == "spec.md:body-drift"
    assert fields["spec.recorded"] != fields["spec.computed"]


def test_design_ux_drift_fails_while_spec_matches(tmp_path):
    change_dir = make_valid_change(tmp_path, design_body=DESIGN_BODY)
    (change_dir / "design-ux.md").write_text(DESIGN_BODY + "x", encoding="utf-8")
    proc = run_check(tmp_path)
    assert proc.returncode != 0
    word, fields = verdict_fields(proc.stdout)
    assert word == "FAIL"
    assert fields["reason"] == "design-ux.md:body-drift"
    assert fields["spec.recorded"] == fields["spec.computed"]


def test_rewritten_fingerprint_matching_a_drifted_body_PASSES_known_residual_hole(tmp_path):
    """KNOWN RESIDUAL HOLE, pinned deliberately so it is not forgotten.

    An agent that holds Bash can drift the body AND rewrite
    `approved_fingerprint` to match it; the recorded and recomputed digests
    then agree and this program reports PASS. Reading the files itself only
    removes the trivial bypass (comparing two agent-supplied strings) — it
    cannot detect a self-consistent forgery. Detecting that needs a trust
    anchor outside the working tree (a signature, or git history), which the
    custody chain does not currently have. If that anchor is ever added,
    this test SHOULD go red — that is the signal, not a regression.
    """
    drifted = SPEC_BODY + "an unapproved extra sentence.\n"
    make_change(
        tmp_path,
        spec=spec_text(body_fingerprint(drifted), "null", body=drifted),
    )
    proc = run_check(tmp_path)
    assert proc.returncode == 0
    word, _ = verdict_fields(proc.stdout)
    assert word == "PASS"


# --------------------------------------------------------------------------
# Recorded-digest shape
# --------------------------------------------------------------------------

def test_malformed_digest_forms_fail(tmp_path):
    real = body_fingerprint(SPEC_BODY)
    cases = {
        "abc": "spec.md:approved_fingerprint-malformed",
        real[:-1]: "spec.md:approved_fingerprint-malformed",  # 63 hex chars
        real + "0": "spec.md:approved_fingerprint-malformed",  # 65 hex chars
        "'not a digest at all'": "spec.md:approved_fingerprint-malformed",
        "": "spec.md:approved_fingerprint-empty",
        "   ": "spec.md:approved_fingerprint-empty",
        "null": "spec.md:approved_fingerprint-empty",
        "~": "spec.md:approved_fingerprint-empty",
    }
    for planted, expected_reason in cases.items():
        change_dir = tmp_path / "STDD" / "some-change"
        if change_dir.exists():
            (change_dir / "spec.md").unlink()
            change_dir.rmdir()
            change_dir.parent.rmdir()
        make_change(tmp_path, spec=spec_text(planted, "null"))
        proc = run_check(tmp_path)
        assert proc.returncode != 0, f"{planted!r} must not pass"
        word, fields = verdict_fields(proc.stdout)
        assert word == "FAIL", f"{planted!r} must not pass"
        assert fields["reason"] == expected_reason, planted


def test_two_matching_garbage_tokens_still_fail(tmp_path):
    """The old comparison passed whenever both sides were equal, garbage
    included. A recorded non-digest is a FAIL regardless of what it equals."""
    make_change(tmp_path, spec=spec_text("abc", "null", body=""))
    proc = run_check(tmp_path)
    assert proc.returncode != 0
    word, fields = verdict_fields(proc.stdout)
    assert word == "FAIL"
    assert fields["reason"] == "spec.md:approved_fingerprint-malformed"


def test_tolerated_digest_spellings_pass_when_genuinely_equal(tmp_path):
    real = body_fingerprint(SPEC_BODY)
    for planted in (
        f"sha256:{real}",
        real.upper(),
        f"{real}  spec.md",  # raw shasum output, filename included
        f'"{real}"',
        f"'{real}'",
        f"sha256:{real.upper()}",
    ):
        change_dir = tmp_path / "STDD" / "some-change"
        if change_dir.exists():
            (change_dir / "spec.md").unlink()
            change_dir.rmdir()
            change_dir.parent.rmdir()
        make_change(tmp_path, spec=spec_text(planted, "null"))
        proc = run_check(tmp_path)
        assert proc.returncode == 0, f"{planted!r}: {proc.stdout}{proc.stderr}"
        word, fields = verdict_fields(proc.stdout)
        assert word == "PASS", planted
        assert fields["spec.recorded"] == real, planted


def test_tolerated_spelling_of_a_wrong_digest_still_fails(tmp_path):
    wrong = "0" * 64
    make_change(tmp_path, spec=spec_text(f"sha256:{wrong.upper()}", "null"))
    proc = run_check(tmp_path)
    assert proc.returncode != 0
    word, fields = verdict_fields(proc.stdout)
    assert word == "FAIL"
    assert fields["reason"] == "spec.md:body-drift"
    assert fields["spec.recorded"] == wrong


# --------------------------------------------------------------------------
# Change-name validation
# --------------------------------------------------------------------------

def test_traversal_and_absolute_change_names_are_refused(tmp_path):
    make_valid_change(tmp_path)
    for name in ("../escape", "/etc", "a/b", "..", ".", "some change", "", "x\ny"):
        proc = run_check(tmp_path, name=name)
        assert proc.returncode != 0, f"{name!r} must be refused"
        word, fields = verdict_fields(proc.stdout)
        assert word == "FAIL", name
        assert fields["reason"] == "change-name:invalid", name
        assert fields["change"] == "-", name


def test_symlinked_change_dir_pointing_out_of_the_root_is_refused(tmp_path):
    outside = tmp_path / "outside"
    make_valid_change(outside)
    (tmp_path / "STDD").mkdir()
    (tmp_path / "STDD" / "some-change").symlink_to(outside / "STDD" / "some-change")
    proc = run_check(tmp_path)
    assert proc.returncode != 0
    word, fields = verdict_fields(proc.stdout)
    assert word == "FAIL"
    assert fields["reason"] == "change-dir:outside-root"


def test_change_dir_symlink_escaping_resolved_root_fails_even_when_target_tree_is_internally_consistent(tmp_path):
    """S-13 case (a): a change directory that is itself a symlink whose
    resolved target sits outside the resolved root MUST fail with the
    determinate reason `change-dir:outside-root` -- even though the target
    tree is internally consistent (its own spec.md fingerprint matches its
    own body). Containment is measured against the resolved root, never
    against whatever the symlink's own target happens to look like."""
    outside = tmp_path / "outside"
    make_valid_change(outside)
    (tmp_path / "STDD").mkdir()
    (tmp_path / "STDD" / "some-change").symlink_to(outside / "STDD" / "some-change")
    proc = run_check(tmp_path)
    assert proc.returncode != 0
    word, fields = verdict_fields(proc.stdout)
    assert word == "FAIL"
    assert fields["reason"] == "change-dir:outside-root"


def test_change_dir_symlink_resolving_inside_root_passes_like_the_projects_own_stdd_to_specs_symlink(tmp_path):
    """S-13 case (b): the change directory is reached through a symlinked
    ancestor (STDD -> specs, the same transitional shape this repo itself
    uses) whose resolution still lands inside -- or equal to -- the
    resolved root. Passing through a symlink is not itself grounds for
    FAIL; the system SHALL PASS here just as it does for a change directory
    reached with no symlink at all."""
    make_valid_change(tmp_path, name="some-change")
    (tmp_path / "STDD").rename(tmp_path / "specs")
    (tmp_path / "STDD").symlink_to(tmp_path / "specs")
    proc = run_check(tmp_path)
    assert proc.returncode == 0
    word, fields = verdict_fields(proc.stdout)
    assert word == "PASS"


def test_refused_name_is_not_interpolated_into_the_verdict_line(tmp_path):
    make_valid_change(tmp_path)
    proc = run_check(tmp_path, name="../../etc")
    assert "../../etc" not in proc.stdout
    assert len(proc.stdout.strip().splitlines()) == 1


# --------------------------------------------------------------------------
# File-level symlink escape (REQ-09) — the change dir itself can pass
# containment while an artifact FILE inside it still points out of root
# --------------------------------------------------------------------------

def test_spec_md_symlink_escaping_root_fails_even_when_directory_containment_passes(tmp_path):
    """S-12: symlink 出 root 的 spec.md 不再 PASS.

    GIVEN <changeDir>/spec.md is a symlink pointing to a file outside the
    resolved root (the external file's own frontmatter/fingerprint is
    internally valid, so directory-level containment on the change dir
    itself has nothing to object to)
    WHEN stdd_custody_check.py <name> --root . runs
    THEN the system SHALL return FAIL with the named reason
    `spec.md:escapes-root`, exit 1 — it SHALL NOT let the containment check
    already passing at directory granularity blind it to the file's own
    symlink target.
    """
    outside_dir = tmp_path.parent / f"{tmp_path.name}-s12-outside"
    outside_dir.mkdir()
    outside_spec = outside_dir / "real-spec.md"
    outside_spec.write_text(spec_text(body_fingerprint(SPEC_BODY), "null"), encoding="utf-8")

    change_dir = make_change(tmp_path)  # no spec/design written directly
    (change_dir / "spec.md").symlink_to(outside_spec)

    proc = run_check(tmp_path)
    assert proc.returncode != 0, proc.stdout + proc.stderr
    word, fields = verdict_fields(proc.stdout)
    assert word == "FAIL"
    assert fields["reason"] == "spec.md:escapes-root"


def test_design_ux_md_symlink_escaping_root_fails_even_when_directory_containment_passes(tmp_path):
    """Mirrors test_spec_md_symlink_escaping_root_fails_even_when_directory_
    containment_passes for the design-ux.md half of the gate.

    GIVEN <changeDir>/design-ux.md is a symlink pointing to a file outside the
    resolved root (the external file's own body is internally consistent, so
    directory-level containment on the change dir itself has nothing to
    object to)
    WHEN stdd_custody_check.py <name> --root . runs
    THEN the system SHALL return FAIL with the named reason
    `design-ux.md:escapes-root`, exit 1 — it SHALL NOT let `is_file()` follow
    the symlink and hash the outside target.
    """
    outside_dir = tmp_path.parent / f"{tmp_path.name}-design-ux-outside"
    outside_dir.mkdir()
    outside_design = outside_dir / "real-design-ux.md"
    outside_design.write_text(DESIGN_BODY, encoding="utf-8")

    change_dir = make_valid_change(tmp_path, design_body=DESIGN_BODY)
    (change_dir / "design-ux.md").unlink()
    (change_dir / "design-ux.md").symlink_to(outside_design)

    proc = run_check(tmp_path)
    assert proc.returncode != 0, proc.stdout + proc.stderr
    word, fields = verdict_fields(proc.stdout)
    assert word == "FAIL"
    assert fields["reason"] == "design-ux.md:escapes-root"


# --------------------------------------------------------------------------
# Degenerate cases — each with its own reason, never a crash, never a pass
# --------------------------------------------------------------------------

def test_missing_change_dir_fails(tmp_path):
    (tmp_path / "STDD").mkdir()
    proc = run_check(tmp_path, name="nope")
    assert proc.returncode != 0
    word, fields = verdict_fields(proc.stdout)
    assert word == "FAIL"
    assert fields["reason"] == "change-dir:missing"


def test_missing_stdd_root_fails(tmp_path):
    proc = run_check(tmp_path)
    assert proc.returncode != 0
    _, fields = verdict_fields(proc.stdout)
    assert fields["reason"] == "change-dir:missing"


def test_missing_spec_md_fails(tmp_path):
    make_change(tmp_path)
    proc = run_check(tmp_path)
    assert proc.returncode != 0
    word, fields = verdict_fields(proc.stdout)
    assert word == "FAIL"
    assert fields["reason"] == "spec.md:missing"
    assert fields["spec.recorded"] == fields["spec.computed"] == "-"


def test_spec_md_without_frontmatter_fails(tmp_path):
    make_change(tmp_path, spec=spec_text(None, frontmatter=False))
    proc = run_check(tmp_path)
    assert proc.returncode != 0
    _, fields = verdict_fields(proc.stdout)
    assert fields["reason"] == "spec.md:no-frontmatter"


def test_unterminated_frontmatter_counts_as_no_frontmatter(tmp_path):
    make_change(tmp_path, spec="---\nstatus: approved\n" + SPEC_BODY)
    proc = run_check(tmp_path)
    assert proc.returncode != 0
    _, fields = verdict_fields(proc.stdout)
    assert fields["reason"] == "spec.md:no-frontmatter"


def test_absent_approved_fingerprint_key_fails(tmp_path):
    make_change(tmp_path, spec=spec_text(None, "null"))
    proc = run_check(tmp_path)
    assert proc.returncode != 0
    _, fields = verdict_fields(proc.stdout)
    assert fields["reason"] == "spec.md:approved_fingerprint-absent"


def test_design_ux_present_without_fingerprint_key_fails(tmp_path):
    make_change(
        tmp_path,
        spec=spec_text(body_fingerprint(SPEC_BODY)),
        design=DESIGN_BODY,
    )
    proc = run_check(tmp_path)
    assert proc.returncode != 0
    _, fields = verdict_fields(proc.stdout)
    assert fields["reason"] == "design-ux.md:fingerprint-absent"


def test_pre_v3_spec_without_design_ux_fingerprint_key_fails(tmp_path):
    make_change(tmp_path, spec=spec_text(body_fingerprint(SPEC_BODY)))
    proc = run_check(tmp_path)
    assert proc.returncode != 0
    _, fields = verdict_fields(proc.stdout)
    assert fields["reason"] == "spec.md:design_ux_fingerprint-absent"


def test_design_ux_fingerprint_recorded_but_file_absent_fails(tmp_path):
    make_change(
        tmp_path,
        spec=spec_text(body_fingerprint(SPEC_BODY), body_fingerprint(DESIGN_BODY)),
    )
    proc = run_check(tmp_path)
    assert proc.returncode != 0
    _, fields = verdict_fields(proc.stdout)
    assert fields["reason"] == "design-ux.md:missing"
    assert fields["design_ux.recorded"] == body_fingerprint(DESIGN_BODY)
    assert fields["design_ux.computed"] == "-"


def test_design_ux_fingerprint_null_but_file_exists_fails(tmp_path):
    make_change(
        tmp_path,
        spec=spec_text(body_fingerprint(SPEC_BODY), "null"),
        design=DESIGN_BODY,
    )
    proc = run_check(tmp_path)
    assert proc.returncode != 0
    _, fields = verdict_fields(proc.stdout)
    assert fields["reason"] == "design-ux.md:not-covered-by-approval"


def test_malformed_design_ux_fingerprint_fails(tmp_path):
    make_change(
        tmp_path,
        spec=spec_text(body_fingerprint(SPEC_BODY), "abc"),
        design=DESIGN_BODY,
    )
    proc = run_check(tmp_path)
    assert proc.returncode != 0
    _, fields = verdict_fields(proc.stdout)
    assert fields["reason"] == "design-ux.md:fingerprint-malformed"


def test_null_design_ux_fingerprint_with_no_file_is_the_legal_no_ui_state(tmp_path):
    for spelling in ("null", "~", "NULL"):
        change_dir = tmp_path / "STDD" / "some-change"
        if change_dir.exists():
            (change_dir / "spec.md").unlink()
            change_dir.rmdir()
            change_dir.parent.rmdir()
        make_change(tmp_path, spec=spec_text(body_fingerprint(SPEC_BODY), spelling))
        proc = run_check(tmp_path)
        assert proc.returncode == 0, f"{spelling}: {proc.stdout}{proc.stderr}"
        word, fields = verdict_fields(proc.stdout)
        assert word == "PASS", spelling
        assert fields["design_ux.recorded"] == "-", spelling


def test_design_ux_path_is_a_directory_fails_instead_of_passing_as_absent(tmp_path):
    """S-14: `design-ux.md` is a directory, not a file, with a null
    `design_ux_fingerprint`. `Path.is_file()` returns False for a directory
    just like it does for a genuinely absent path, so the null-fingerprint
    "no UI surface" PASS branch (see
    test_null_design_ux_fingerprint_with_no_file_is_the_legal_no_ui_state
    above) must not silently swallow this case too. THEN: named reason
    `design-ux.md:not-a-file`, FAIL, exit 1."""
    change_dir = make_change(tmp_path, spec=spec_text(body_fingerprint(SPEC_BODY), "null"))
    (change_dir / "design-ux.md").mkdir()
    proc = run_check(tmp_path)
    assert proc.returncode != 0
    word, fields = verdict_fields(proc.stdout)
    assert word == "FAIL"
    assert fields["reason"] == "design-ux.md:not-a-file"


def test_duplicate_frontmatter_key_fails_instead_of_silently_last_wins(tmp_path):
    """S-18: `spec.md`'s frontmatter carries the top-level `approved_fingerprint:`
    key twice, with two different values. `frontmatter_fields` today just
    overwrites the dict entry on the second occurrence
    (`fields[key.strip()] = value.strip()`), so the check silently adopts the
    LAST value and falls through to the normal PASS/FAIL digest comparison
    instead of naming the duplication. THEN: a named-reason FAIL, exit 1 —
    not a silent last-wins PASS/FAIL."""
    first_fp = body_fingerprint(SPEC_BODY)
    second_fp = body_fingerprint(SPEC_BODY + "x")
    spec = (
        "---\n"
        "status: approved\n"
        "approved_date: 2026-01-01\n"
        f"approved_fingerprint: {first_fp}\n"
        f"approved_fingerprint: {second_fp}\n"
        "design_ux_fingerprint: null\n"
        "---\n" + SPEC_BODY
    )
    make_change(tmp_path, spec=spec)
    proc = run_check(tmp_path)
    assert proc.returncode != 0, proc.stdout + proc.stderr
    word, fields = verdict_fields(proc.stdout)
    assert word == "FAIL"
    assert fields["reason"] == "spec.md:frontmatter-duplicate-key"


def test_frontmatter_line_without_colon_separator_is_skipped_safely(tmp_path):
    """S-21: `spec.md`'s frontmatter carries a legal `approved_fingerprint:`
    line immediately followed by one line with no `:` separator at all (a
    malformed key line), with the rest of the block otherwise legal.
    `frontmatter_fields` (scripts/stdd_custody_check.py:127-129) partitions
    each line on `:` and does `if not sep: continue` when no separator is
    found — the no-colon line SHALL be skipped without raising, and the
    surrounding legal `key: value` fields (including `approved_fingerprint`)
    SHALL still parse correctly. THEN: no crash, and a PASS verdict driven
    by the correctly-parsed `approved_fingerprint`."""
    fp = body_fingerprint(SPEC_BODY)
    spec = (
        "---\n"
        "status: approved\n"
        "approved_date: 2026-01-01\n"
        f"approved_fingerprint: {fp}\n"
        "this line has no colon separator at all\n"
        "design_ux_fingerprint: null\n"
        "---\n" + SPEC_BODY
    )
    make_change(tmp_path, spec=spec)
    proc = run_check(tmp_path)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    word, fields = verdict_fields(proc.stdout)
    assert word == "PASS"
    assert fields["spec.recorded"] == fp
    assert fields["spec.computed"] == fp


@pytest.mark.skipif(os.geteuid() == 0, reason="chmod 000 is a no-op for root")
def test_unreadable_spec_md_fails_with_change_dir_unreadable_reason(tmp_path):
    """S-20: an otherwise-valid change directory whose `spec.md` is
    `chmod 000`'d (unreadable to a non-root caller) must reach `main()`'s
    `except OSError` branch and print exactly
    `CUSTODY: FAIL reason=change-dir:unreadable`, exit 1 — never an
    uncaught traceback and never a fall-through to PASS."""
    change_dir = make_valid_change(tmp_path)
    spec_path = change_dir / "spec.md"
    spec_path.chmod(0o000)
    try:
        proc = run_check(tmp_path)
    finally:
        spec_path.chmod(0o644)
    assert proc.returncode == 1, proc.stdout + proc.stderr
    assert "Traceback" not in proc.stderr
    word, fields = verdict_fields(proc.stdout)
    assert word == "FAIL"
    assert fields["reason"] == "change-dir:unreadable"


# --------------------------------------------------------------------------
# Read-only guarantee
# --------------------------------------------------------------------------

def test_run_does_not_modify_the_change_tree(tmp_path):
    change_dir = make_valid_change(tmp_path, design_body=DESIGN_BODY)

    def snapshot():
        return {
            path.relative_to(tmp_path).as_posix(): hashlib.sha256(
                path.read_bytes()
            ).hexdigest()
            for path in sorted((tmp_path / "STDD").rglob("*"))
            if path.is_file()
        }

    before = snapshot()
    assert run_check(tmp_path).returncode == 0
    run_check(tmp_path, name="nope")
    assert snapshot() == before
    assert sorted(p.name for p in change_dir.iterdir()) == ["design-ux.md", "spec.md"]


# --------------------------------------------------------------------------
# TASKS: line (S-28)
# --------------------------------------------------------------------------

TASKS_BODY = """\
# Tasks

這份文件說明「`- [x]` 代表完成」的意思，這只是 prose 敘述，不是任務行。

- [ ] `S-01` do the first open thing
- [wip] `S-02` do the second thing, currently in progress
- [x] `S-03` the third thing is already done
- [ ] `S-04` `[MANUAL]` a fourth open thing that needs a human hand
- [x] `S-05` `[INFRA]` a fifth, already-done infra thing

```mermaid
graph TD
  N1 --> N2[INFRA]
```

- [X] `S-99` capital X must not count as done (grammar is case-sensitive)
- [ ] (no id here, so this is not a formal task line either)
"""


def run_check_change_dir(change_dir):
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), "--change-dir", str(change_dir)],
        capture_output=True,
        text=True,
    )
    return proc


# --------------------------------------------------------------------------
# `--change-dir` mode (REQ-07 CLI contract, S-09/S-19/S-21/S-30)
# --------------------------------------------------------------------------

def test_change_dir_mode_produces_the_identical_verdict_grammar_as_legacy_root_mode(tmp_path):
    """REQ-07 D-13: `--change-dir <abs>` (primary mode) and the positional
    `<name> --root <dir>` form (legacy mode) SHALL produce the identical
    verdict-line grammar for the same underlying change. `change=` in
    `--change-dir` mode is the change directory's own last path segment
    (D-14/F-02), never a separately-typed name."""
    change_dir = make_valid_change(tmp_path, name="some-change", design_body=DESIGN_BODY)

    legacy_proc = run_check(tmp_path, name="some-change")
    change_dir_proc = run_check_change_dir(change_dir)

    assert legacy_proc.returncode == 0, legacy_proc.stdout + legacy_proc.stderr
    assert change_dir_proc.returncode == 0, change_dir_proc.stdout + change_dir_proc.stderr
    assert change_dir_proc.stdout == legacy_proc.stdout, (
        f"--change-dir mode stdout ({change_dir_proc.stdout!r}) should match legacy mode's "
        f"({legacy_proc.stdout!r}) byte for byte"
    )


def test_change_dir_mode_and_legacy_positional_together_is_an_argparse_error_exit_2(tmp_path):
    """REQ-07 D-13: supplying both `--change-dir` and the positional change
    name together is an argparse error, exit 2, with no `CUSTODY:` verdict
    line printed at all — this is not a verdict, callers must not confuse it
    with one."""
    change_dir = make_valid_change(tmp_path)
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), "some-change", "--change-dir", str(change_dir)],
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 2, proc.stdout + proc.stderr
    assert "CUSTODY:" not in proc.stdout


def test_change_dir_mode_and_legacy_root_flag_together_is_an_argparse_error_exit_2(tmp_path):
    """REQ-07 D-13: `--change-dir` together with `--root` (the legacy mode's
    own flag, without a positional change name) is likewise mutually
    exclusive — exit 2, no verdict line."""
    change_dir = make_valid_change(tmp_path)
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), "--change-dir", str(change_dir), "--root", str(tmp_path)],
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 2, proc.stdout + proc.stderr
    assert "CUSTODY:" not in proc.stdout


def test_change_dir_mode_with_relative_path_fails_not_absolute(tmp_path):
    """`--change-dir` mode requires an absolute path — the workflow-side
    caller is responsible for confirming and resolving it (REQ-18); a
    relative value is a named FAIL, not silently resolved against cwd."""
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), "--change-dir", "some-change"],
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 1, proc.stdout + proc.stderr
    word, fields = verdict_fields(proc.stdout)
    assert word == "FAIL"
    assert fields["reason"] == "change-dir:not-absolute"


def test_change_dir_mode_nonexistent_directory_fails_spec_md_missing(tmp_path):
    """S-09/S-23(b) fixture: an absolute `--change-dir` pointing at a
    directory that does not exist FAILs `spec.md:missing` — the same
    fail-closed reason the workflow's own S-23 acceptance criterion relies
    on."""
    missing_dir = tmp_path / "does-not-exist"
    proc = run_check_change_dir(missing_dir)
    assert proc.returncode == 1, proc.stdout + proc.stderr
    word, fields = verdict_fields(proc.stdout)
    assert word == "FAIL"
    assert fields["reason"] == "spec.md:missing"


def test_change_dir_mode_change_token_is_the_directories_own_last_path_segment(tmp_path):
    """D-14/F-02: `change=` in `--change-dir` mode comes from
    `Path(change_dir).resolve().name` — the directory's own last segment —
    even when it differs from the tmp_path fixture's nominal `name` kwarg
    used only to build the tree."""
    change_dir = make_valid_change(tmp_path, name="literally-anything")
    proc = run_check_change_dir(change_dir)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    _, fields = verdict_fields(proc.stdout)
    assert fields["change"] == "literally-anything"


def test_tasks_line_counts_open_wip_done_manual_infra_tags_and_ids_correctly_ignoring_non_task_lines(tmp_path):
    """S-28: `stdd_custody_check.py` must print, immediately after the
    `CUSTODY:` verdict line, a second line
    `TASKS: open=<n> wip=<n> done=<n> manual=<n> infra=<n> ids=<id>(;<id>)*`
    (v0.7.3: the inter-task separator is `;`, not `,` — a comma is reserved
    for joining the sub-ids of a single merged task, e.g. `S-03,S-04`, so a
    plain comma between two ids can no longer be mistaken for a merged id's
    internal separator)
    whose five counts and `ids` list match only the FORMAL task lines in
    `tasks.md` — lines matching `^- \\[( |wip|x)\\] ` immediately followed by
    a backtick-wrapped id — in file order. Non-task lines that merely
    contain marker/tag-looking text (prose quoting `- [x]`, a mermaid node
    label `[INFRA]`, an uppercase `[X]` marker, or a checkbox with no id)
    must NOT be counted."""
    change_dir = make_valid_change(tmp_path)
    (change_dir / "tasks.md").write_text(TASKS_BODY, encoding="utf-8")
    proc = run_check(tmp_path)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    lines = proc.stdout.splitlines()
    assert len(lines) >= 2, (
        "expected a TASKS: line right after CUSTODY:, got:\n" + proc.stdout
    )
    assert lines[0].startswith("CUSTODY: "), lines[0]
    assert lines[1] == (
        "TASKS: open=2 wip=1 done=2 manual=1 infra=1 "
        "ids=S-01;S-02;S-03;S-04;S-05"
    ), lines[1]


def test_task_id_containing_whitespace_fails_instead_of_emitting_a_malformed_tasks_line(tmp_path):
    """A tasks.md id containing a space violates this file's own documented
    invariant ("every field is a whitespace-free key=value token") and would
    fail the consumer's TASKS_LINE_RE, producing a load-side block whose
    remedy ("upgrade stdd_custody_check.py to print the TASKS: count line")
    can never be satisfied since the line WAS printed. The script must catch
    this itself and FAIL with a named reason instead of ever emitting a
    malformed ids= token."""
    change_dir = make_valid_change(tmp_path)
    (change_dir / "tasks.md").write_text(
        "# Tasks\n\n- [ ] `S 01` an id with an embedded space\n",
        encoding="utf-8",
    )
    proc = run_check(tmp_path)
    assert proc.returncode == 1, proc.stdout + proc.stderr
    word, fields = verdict_fields(proc.stdout)
    assert word == "FAIL"
    assert fields["reason"] == "tasks.md:unsafe-task-id"
    assert "TASKS:" not in proc.stdout


def test_indented_task_shaped_line_fails_instead_of_being_silently_dropped(tmp_path):
    """A task line indented under leading whitespace is invisible to
    TASK_LINE_RE's column-0 anchor. Silently ignoring it would let a wip/open
    task disappear from the counted total with no signal at all — the exact
    failure the reconciliation exists to catch — so an indented but
    otherwise task-shaped line must FAIL loudly instead."""
    change_dir = make_valid_change(tmp_path)
    (change_dir / "tasks.md").write_text(
        "# Tasks\n\n- [ ] `S-01` a normal top-level task\n"
        "  - [wip] `S-02` an indented task-shaped line\n",
        encoding="utf-8",
    )
    proc = run_check(tmp_path)
    assert proc.returncode == 1, proc.stdout + proc.stderr
    word, fields = verdict_fields(proc.stdout)
    assert word == "FAIL"
    assert fields["reason"] == "tasks.md:indented-task-line"
    assert "TASKS:" not in proc.stdout


# --------------------------------------------------------------------------
# Council round 3 defects (P1-P6)
# --------------------------------------------------------------------------

def test_bom_prefixed_tasks_md_counts_both_tasks_not_just_the_second(tmp_path):
    """P1: a UTF-8 BOM at the start of tasks.md must not make line 1 invisible
    to TASK_LINE_RE — otherwise an open task silently vanishes and the
    verdict still reports PASS with an undercounted TASKS: line."""
    change_dir = make_valid_change(tmp_path)
    (change_dir / "tasks.md").write_bytes(
        "﻿- [ ] `t1` first task\n- [x] `t2` second task\n".encode("utf-8")
    )
    proc = run_check(tmp_path)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    lines = proc.stdout.splitlines()
    assert lines[1] == "TASKS: open=1 wip=0 done=1 manual=0 infra=0 ids=t1;t2", lines[1]


def test_undecodable_tasks_md_fails_with_a_named_reason_instead_of_a_traceback(tmp_path):
    """P2: invalid UTF-8 bytes in tasks.md must never produce a bare
    UnicodeDecodeError traceback and no CUSTODY: line at all — the docstring
    promises a verdict is always printed, never a fall-through crash."""
    change_dir = make_valid_change(tmp_path)
    (change_dir / "tasks.md").write_bytes(b"- [ ] `T-1`\n\xff\xfe bad\n")
    proc = run_check(tmp_path)
    assert proc.returncode == 1, proc.stdout + proc.stderr
    word, fields = verdict_fields(proc.stdout)
    assert word == "FAIL"
    assert fields["reason"] == "tasks.md:undecodable"
    assert "Traceback" not in proc.stderr


def test_symlinked_tasks_md_escaping_root_fails_instead_of_reading_the_outside_file(tmp_path):
    """P3: tasks.md gets no symlink containment check today, so a
    reconciliation baseline can be sourced from a file outside the change
    dir's root. Must FAIL like spec.md/design-ux.md's own escapes-root
    checks."""
    outside_dir = tmp_path.parent / f"{tmp_path.name}-tasks-outside"
    outside_dir.mkdir()
    outside_tasks = outside_dir / "real-tasks.md"
    outside_tasks.write_text("- [ ] `t1` outside task\n", encoding="utf-8")

    change_dir = make_valid_change(tmp_path)
    (change_dir / "tasks.md").symlink_to(outside_tasks)

    proc = run_check(tmp_path)
    assert proc.returncode == 1, proc.stdout + proc.stderr
    word, fields = verdict_fields(proc.stdout)
    assert word == "FAIL"
    assert fields["reason"] == "tasks.md:escapes-root"


def test_task_shaped_lines_inside_a_fenced_code_block_are_not_counted(tmp_path):
    """P4: a fenced example block (containing a task-shaped line AND an
    illegal id) must not be scanned as real tasks — the framework's own docs
    contain such examples, and counting them either double-counts or hard-
    fails the whole change on a documentation example."""
    change_dir = make_valid_change(tmp_path)
    (change_dir / "tasks.md").write_text(
        "# Tasks\n\n"
        "- [ ] `t1` a real task\n\n"
        "```\n"
        "- [ ] `t9` example line inside a fence\n"
        "- [x] `bad id` illegal id, also inside the fence\n"
        "```\n",
        encoding="utf-8",
    )
    proc = run_check(tmp_path)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    lines = proc.stdout.splitlines()
    assert lines[1] == "TASKS: open=1 wip=0 done=0 manual=0 infra=0 ids=t1", lines[1]


def test_task_id_with_a_leading_dash_fails_instead_of_emitting_a_flag_like_token(tmp_path):
    """P5: `ids=-t1` passes TASK_ID_RE today but a leading dash is a flag to
    any downstream CLI consumer reading the TASKS: line's ids= token. Must
    FAIL with the existing unsafe-task-id reason, not print it."""
    change_dir = make_valid_change(tmp_path)
    (change_dir / "tasks.md").write_text(
        "- [ ] `-t1` a task whose id starts with a dash\n", encoding="utf-8"
    )
    proc = run_check(tmp_path)
    assert proc.returncode == 1, proc.stdout + proc.stderr
    word, fields = verdict_fields(proc.stdout)
    assert word == "FAIL"
    assert fields["reason"] == "tasks.md:unsafe-task-id"
    assert "TASKS:" not in proc.stdout


# --------------------------------------------------------------------------
# M4: merged-task ids (stdd-plan's module-convergence rule, e.g. `S-03,S-04`)
# --------------------------------------------------------------------------

def test_merged_task_id_passes_custody_and_keeps_its_internal_comma_in_ids(tmp_path):
    """A merged task id is a comma-joined list of per-token ids, each of which
    individually matches TASK_ID_RE — the JS side (workflows/stdd-execute.js)
    already accepts this per-token, so the custody script must stop
    hard-FAILing it as `unsafe-task-id` before build_tasks_line even runs.
    The inter-TASK separator stays `;`, so the merged id's own `,` survives
    unescaped inside a single `ids=` token."""
    change_dir = make_valid_change(tmp_path)
    (change_dir / "tasks.md").write_text(
        "# Tasks\n\n"
        "- [ ] `S-03,S-04` a module-convergence merged task\n"
        "- [x] `S-05` a plain task\n",
        encoding="utf-8",
    )
    proc = run_check(tmp_path)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    lines = proc.stdout.splitlines()
    assert lines[1] == (
        "TASKS: open=1 wip=0 done=1 manual=0 infra=0 ids=S-03,S-04;S-05"
    ), lines[1]


def test_merged_task_id_with_a_trailing_comma_fails_as_unsafe_task_id(tmp_path):
    """A trailing comma splits into an empty final token, which TASK_ID_RE
    (requiring 1+ chars) rejects — the merged-id acceptance must not paper
    over a degenerate empty token."""
    change_dir = make_valid_change(tmp_path)
    (change_dir / "tasks.md").write_text(
        "- [ ] `S-03,` a task id with a trailing comma\n", encoding="utf-8"
    )
    proc = run_check(tmp_path)
    assert proc.returncode == 1, proc.stdout + proc.stderr
    word, fields = verdict_fields(proc.stdout)
    assert word == "FAIL"
    assert fields["reason"] == "tasks.md:unsafe-task-id"
    assert "TASKS:" not in proc.stdout


def test_merged_task_id_with_a_double_comma_fails_as_unsafe_task_id(tmp_path):
    """A double comma splits into an empty middle token, same as a trailing
    comma — must fail, not be silently treated as a two-token merge."""
    change_dir = make_valid_change(tmp_path)
    (change_dir / "tasks.md").write_text(
        "- [ ] `S-03,,S-04` a task id with an empty middle token\n",
        encoding="utf-8",
    )
    proc = run_check(tmp_path)
    assert proc.returncode == 1, proc.stdout + proc.stderr
    word, fields = verdict_fields(proc.stdout)
    assert word == "FAIL"
    assert fields["reason"] == "tasks.md:unsafe-task-id"
    assert "TASKS:" not in proc.stdout


def test_merged_task_id_with_a_traversal_token_fails_as_unsafe_task_id(tmp_path):
    """Splitting on `,` must validate EVERY resulting token against the
    unchanged TASK_ID_RE — a garbage second token like `../x` must still
    block the whole id, not slip through because the first token looked
    fine."""
    change_dir = make_valid_change(tmp_path)
    (change_dir / "tasks.md").write_text(
        "- [ ] `S-03,../x` a task id whose second token escapes the charset\n",
        encoding="utf-8",
    )
    proc = run_check(tmp_path)
    assert proc.returncode == 1, proc.stdout + proc.stderr
    word, fields = verdict_fields(proc.stdout)
    assert word == "FAIL"
    assert fields["reason"] == "tasks.md:unsafe-task-id"
    assert "TASKS:" not in proc.stdout


def test_tasks_md_with_zero_formal_task_lines_fails_with_a_named_reason(tmp_path):
    """P6: a tasks.md that exists but carries zero formal task lines must not
    emit an unparseable empty `ids=` TASKS: line (which the workflow-side
    consumer rejects with a wrong remedy claiming the count line was never
    printed, when it was). Must FAIL with a named reason instead."""
    change_dir = make_valid_change(tmp_path)
    (change_dir / "tasks.md").write_text(
        "# Tasks\n\nNo formal task lines here, just prose.\n", encoding="utf-8"
    )
    proc = run_check(tmp_path)
    assert proc.returncode == 1, proc.stdout + proc.stderr
    word, fields = verdict_fields(proc.stdout)
    assert word == "FAIL"
    assert fields["reason"] == "tasks.md:no-tasks"
    assert "TASKS:" not in proc.stdout


def test_absent_tasks_md_prints_a_literal_tasks_missing_line(tmp_path):
    """REQ-20 (spec.md:1121), user decision: when tasks.md is ABSENT
    entirely, the program must no longer stay silent — it SHALL print the
    literal line `TASKS: missing` as the second stdout line, in the same
    position the normal TASKS: count line occupies. The custody chain itself
    (spec.md/design-ux.md) is unaffected by a change carrying no tasks.md, so
    the CUSTODY: verdict stays PASS/exit 0 — `TASKS: missing` is reported
    independently, exactly like the normal TASKS: count line is. The
    workflow side (not this script) is what blocks before calling
    `loadChange` when it sees this literal."""
    make_valid_change(tmp_path)
    proc = run_check(tmp_path)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    lines = proc.stdout.splitlines()
    assert lines[0].startswith("CUSTODY: PASS"), lines[0]
    assert len(lines) >= 2, (
        "expected a TASKS: missing line right after CUSTODY:, got:\n" + proc.stdout
    )
    assert lines[1] == "TASKS: missing", lines[1]


def test_absent_tasks_md_missing_line_carries_no_trailing_tokens(tmp_path):
    """Companion to the above: `TASKS: missing` is a LITERAL, not a
    `key=value` line — it must never grow a trailing token (a stray count,
    a reason=, whitespace), since the JS side matches it as an exact
    string, not via TASKS_LINE_RE (which this literal does not satisfy)."""
    make_valid_change(tmp_path)
    proc = run_check(tmp_path)
    lines = proc.stdout.splitlines()
    assert lines[1] == "TASKS: missing"
    assert not lines[1].endswith(" "), "no trailing whitespace"
    assert len(lines) == 2, f"expected exactly 2 stdout lines, got: {lines!r}"


# --------------------------------------------------------------------------
# M13: the complete set of `reason=<token>` values the program can emit
# --------------------------------------------------------------------------

# Every reason token this file's individual scenario tests already pin,
# above, one by one. This is the single place the FULL set is enumerated —
# a future reason string added to (or renamed in) the script without a
# matching update here fails this test loudly, instead of silently drifting
# from the code (M13). Kept as a hardcoded literal set, not derived from the
# script by import, per this file's own black-box-subprocess convention.
EXPECTED_REASON_TOKENS = {
    "change-dir:missing",
    "change-dir:not-absolute",
    "change-dir:outside-root",
    "change-dir:unreadable",
    "change-name:invalid",
    "design-ux.md:body-drift",
    "design-ux.md:escapes-root",
    "design-ux.md:fingerprint-absent",
    "design-ux.md:fingerprint-malformed",
    "design-ux.md:missing",
    "design-ux.md:not-a-file",
    "design-ux.md:not-covered-by-approval",
    "spec.md:approved_fingerprint-absent",
    "spec.md:approved_fingerprint-empty",
    "spec.md:approved_fingerprint-malformed",
    "spec.md:body-drift",
    "spec.md:design_ux_fingerprint-absent",
    "spec.md:escapes-root",
    "spec.md:frontmatter-duplicate-key",
    "spec.md:missing",
    "spec.md:no-frontmatter",
    "tasks.md:escapes-root",
    "tasks.md:indented-task-line",
    "tasks.md:no-tasks",
    "tasks.md:undecodable",
    "tasks.md:unsafe-task-id",
}

# A `reason=<token>` literal as it appears in the script's source: a quoted
# string of the `<artifact>:<problem>` shape (module docstring, "Every field
# is a whitespace-free key=value token... <token> is a whitespace-free
# reason of the form <artifact>:<problem>"). Deliberately the same character
# class the script's own CHANGE_NAME_RE/TASK_ID_RE use on each side of the
# colon, so this scan cannot accidentally pick up an unrelated quoted string.
REASON_TOKEN_LITERAL_RE = re.compile(r'"([A-Za-z0-9._-]+:[A-Za-z0-9._-]+)"')


def scan_reason_tokens_from_source():
    """Every reason token literal the script's source actually contains,
    found by reading the file as text (no import — this test stays
    black-box like the rest of the file)."""
    text = SCRIPT.read_text(encoding="utf-8")
    return set(REASON_TOKEN_LITERAL_RE.findall(text))


# D3: matches `const CUSTODY_FAIL_RE = /.../;` tolerant of whitespace/line-
# breaks around the `=` and between the declaration and the regex literal —
# a harmless reformat of that line must not silently break this
# cross-language extraction. The regex-literal group intentionally forbids
# an unescaped `/` or newline inside it (mirroring how a JS regex literal
# itself cannot contain either), so this cannot accidentally swallow
# unrelated source past the real declaration.
CUSTODY_FAIL_RE_DECLARATION_RE = re.compile(
    r"const\s+CUSTODY_FAIL_RE\s*=\s*(/(?:[^/\\\n]|\\.)*/)\s*;", re.DOTALL
)


def extract_custody_fail_re(text=None):
    """The REAL `CUSTODY_FAIL_RE` regex from workflows/stdd-execute.js,
    extracted from its source text (not re-typed by hand), so this test
    checks the actual consumer pattern rather than a drifted copy of it.
    `text` is injectable for testing extraction tolerance; defaults to the
    real file."""
    if text is None:
        js_path = REPO_ROOT / "workflows" / "stdd-execute.js"
        text = js_path.read_text(encoding="utf-8")
    match = CUSTODY_FAIL_RE_DECLARATION_RE.search(text)
    assert match, "CUSTODY_FAIL_RE definition not found in stdd-execute.js"
    literal = match.group(1)
    pattern = literal[1:-1]
    return re.compile(pattern)


def test_reason_token_set_matches_the_scripts_source_exactly():
    """M13: pins the COMPLETE set of reason tokens, not scattered per-string
    assertions — a token added, removed, or renamed in the script without a
    matching update here fails this one test instead of drifting quietly."""
    found = scan_reason_tokens_from_source()
    assert found == EXPECTED_REASON_TOKENS, (
        f"new tokens: {found - EXPECTED_REASON_TOKENS}; "
        f"missing tokens: {EXPECTED_REASON_TOKENS - found}"
    )


def test_every_reason_token_matches_the_js_sides_custody_fail_re():
    """Every reason token above, embedded in a full CUSTODY: FAIL line, must
    still match the real `CUSTODY_FAIL_RE` from workflows/stdd-execute.js —
    verified against the ACTUAL regex object extracted from that file, not a
    hand-copied restatement of it."""
    custody_fail_re = extract_custody_fail_re()
    digest = "a" * 64
    for token in EXPECTED_REASON_TOKENS:
        line = (
            f"CUSTODY: FAIL reason={token} change=some-change "
            f"spec.recorded={digest} spec.computed={digest} "
            f"design_ux.recorded={digest} design_ux.computed={digest}"
        )
        match = custody_fail_re.match(line)
        assert match is not None, f"{token!r} does not match CUSTODY_FAIL_RE"
        assert match.group(1) == token


def test_extract_custody_fail_re_tolerates_a_reflowed_declaration():
    """D3: extract_custody_fail_re() was glued to the exact literal
    formatting `const CUSTODY_FAIL_RE =\\n` — a harmless reformat of that
    line (e.g. onto one line, or with different whitespace) would silently
    break this cross-language guarantee without failing loudly. Reflow the
    REAL declaration (never a hand-retyped copy of the pattern) onto one
    line with irregular whitespace, and confirm extraction still finds and
    compiles the actual regex."""
    js_path = REPO_ROOT / "workflows" / "stdd-execute.js"
    original_text = js_path.read_text(encoding="utf-8")
    marker = "const CUSTODY_FAIL_RE =\n"
    assert marker in original_text, "fixture assumption: current declaration shape"
    start = original_text.index(marker) + len(marker)
    end = original_text.index("\n", start)
    real_declaration_line = original_text[start:end].strip()  # the REAL "/pattern/;" text
    reflowed_text = (
        original_text[: original_text.index(marker)]
        + "const   CUSTODY_FAIL_RE\t=   "
        + real_declaration_line
        + "\n"
        + original_text[end + 1 :]
    )

    custody_fail_re = extract_custody_fail_re(reflowed_text)

    digest = "a" * 64
    token = "spec.md:missing"
    line = (
        f"CUSTODY: FAIL reason={token} change=some-change "
        f"spec.recorded={digest} spec.computed={digest} "
        f"design_ux.recorded={digest} design_ux.computed={digest}"
    )
    match = custody_fail_re.match(line)
    assert match is not None, "extraction should still find CUSTODY_FAIL_RE in the reflowed declaration"
    assert match.group(1) == token
