# -*- coding: utf-8 -*-
"""Doc-consistency checks for skills/tlor-init/SKILL.md.

These are plain text-content assertions against the real, checked-in
SKILL.md file (not a synthetic fixture) — the thing under test IS the
document, so there is nothing to invoke as a subprocess.
"""
import re

from conftest import REPO_ROOT

SKILL_MD = REPO_ROOT / "skills" / "tlor-init" / "SKILL.md"

PLAN_SKILL = REPO_ROOT / "stdd-skills" / "stdd-plan" / "SKILL.md"
EXECUTE_SKILL = REPO_ROOT / "stdd-skills" / "stdd-execute" / "SKILL.md"
CUSTODY_CHECK = REPO_ROOT / "scripts" / "stdd_custody_check.py"
EXECUTE_WORKFLOW = REPO_ROOT / "workflows" / "stdd-execute.js"

# The approved canonical source (fix-execute-review-findings/spec.md, B2/B3
# Decision Outcome, Option 1): stdd-skills/stdd-spec/SKILL.md Step 6.
CANONICAL = "stdd-spec/SKILL.md"

# Old canonical declaration withdrawn by the same decision -- must not
# survive as a custody/status-semantics pointer anywhere.
WITHDRAWN = "checklist.md"


def test_all_custody_status_citations_point_to_the_approved_canonical_file():
    """fix-execute-review-findings/spec.md S-05.

    GIVEN the B2/B3 decision already approves `stdd-skills/stdd-spec/SKILL.md`
    Step 6 as the one canonical file for custody/status semantics
    WHEN grepping `stdd-plan/SKILL.md`, `stdd-execute/SKILL.md`,
    `scripts/stdd_custody_check.py`, and `workflows/stdd-execute.js`'s
    `meta.whenToUse` for custody/status semantics citations and directory-
    layout strings
    THEN every citation SHALL name that one approved source, none SHALL
    still point at the withdrawn `checklist.md` declaration or at each
    other, and `meta.whenToUse` SHALL NOT still carry the stale
    `STDD/<name>` layout string
    """
    plan_text = PLAN_SKILL.read_text(encoding="utf-8")
    execute_text = EXECUTE_SKILL.read_text(encoding="utf-8")
    custody_text = CUSTODY_CHECK.read_text(encoding="utf-8")
    workflow_text = EXECUTE_WORKFLOW.read_text(encoding="utf-8")

    sites = {
        "stdd-plan/SKILL.md": plan_text,
        "stdd-execute/SKILL.md": execute_text,
        "scripts/stdd_custody_check.py": custody_text,
    }

    # 1. No site's custody/status canonical declaration still names the
    #    withdrawn checklist.md source.
    for name, text in sites.items():
        for line in text.splitlines():
            if "canonical" in line and WITHDRAWN in line:
                raise AssertionError(
                    f"{name} still names the withdrawn canonical source "
                    f"({WITHDRAWN!r}) on a canonical-labeled line: {line!r}"
                )

    # 2. Every site cites the SAME approved canonical file.
    for name, text in sites.items():
        assert CANONICAL in text, (
            f"{name} does not cite the approved canonical source "
            f"({CANONICAL!r}) anywhere"
        )

    # 3. custody_check.py's fingerprint-definition block must name only ONE
    #    canonical file, not several different SKILL.md files.
    fingerprint_block_match = re.search(
        r"Fingerprint definition.*?\n\n", custody_text, re.DOTALL
    )
    assert fingerprint_block_match, (
        "scripts/stdd_custody_check.py: could not find the 'Fingerprint "
        "definition' comment block to check"
    )
    block = fingerprint_block_match.group(0)
    canonical_file_mentions = set(
        re.findall(r"stdd-skills/([a-z0-9-]+)/SKILL\.md", block)
    )
    assert canonical_file_mentions == {"stdd-spec"}, (
        "scripts/stdd_custody_check.py's fingerprint-definition block cites "
        f"{sorted(canonical_file_mentions)} as canonical sources instead of "
        "the single approved stdd-spec/SKILL.md"
    )

    # 4. workflows/stdd-execute.js meta.whenToUse must not carry the stale
    #    STDD/<name> layout string.
    when_to_use_match = re.search(r"whenToUse:\s*\n?\s*'([^']*)'", workflow_text)
    assert when_to_use_match, (
        "workflows/stdd-execute.js: could not find meta.whenToUse to check"
    )
    when_to_use = when_to_use_match.group(1)
    assert "STDD/<name>" not in when_to_use, (
        "workflows/stdd-execute.js meta.whenToUse still uses the stale "
        f"'STDD/<name>' layout string: {when_to_use!r}"
    )


# An "exit 0 = PASS" claim: "exit code|status" (optionally) followed
# directly by the digit 0, then PASS within a short window. The window is
# captured (not just matched) so the qualifier check below can inspect
# exactly what sits between the "0" and "PASS" -- inserting the required
# "CUSTODY:" qualifier there is what turns a violation into compliant text.
EXIT_ZERO_PASS_CLAIM_RE = re.compile(
    r"exit\s+(?:code|status)?\s*:?\s*0\b(?P<between>.{0,60}?)\bPASS\b",
    re.IGNORECASE | re.DOTALL,
)


def _unqualified_exit_zero_pass_claims(text):
    """Return every "exit 0 = PASS" claim in `text` that does not qualify
    itself with the CUSTODY: verdict-line requirement in between."""
    violations = []
    for match in EXIT_ZERO_PASS_CLAIM_RE.finditer(text):
        if "CUSTODY" not in match.group("between").upper():
            violations.append(match.group(0))
    return violations


def test_exit_0_means_pass_wording_always_qualifies_a_custody_verdict_line():
    """fix-execute-review-findings/spec.md S-08.

    GIVEN `stdd-skills/stdd-execute/SKILL.md` and
      `scripts/stdd_custody_check.py`'s module docstring, wherever either
      describes "exit 0 means PASS"
    WHEN reading these files' content and comparing the wording
    THEN every such sentence SHALL be rewritten to "exit 0 with a CUSTODY:
      verdict line means PASS" -- no site SHALL still state a bare "exit 0
      means PASS" that does not qualify itself with the CUSTODY: verdict
      line.
    """
    sites = {
        "stdd-skills/stdd-execute/SKILL.md": EXECUTE_SKILL.read_text(encoding="utf-8"),
        "scripts/stdd_custody_check.py": CUSTODY_CHECK.read_text(encoding="utf-8"),
    }

    for name, text in sites.items():
        violations = _unqualified_exit_zero_pass_claims(text)
        assert not violations, (
            f"{name} still states 'exit 0 means PASS' without qualifying it "
            f"with the CUSTODY: verdict-line requirement: {violations!r}"
        )


def test_tlor_init_step3_summary_reference_matches_actual_step_number():
    """S-17: Step 3 的摘要交代引用與實際的摘要章節編號一致.

    GIVEN skills/tlor-init/SKILL.md's current section numbering
      (`### Step 12: Report summary`)
    WHEN reading Step 3's "Report each file's outcome ... for Step X's
      summary" sentence
    THEN the referenced number X SHALL match the actual summary section
      number.
    """
    text = SKILL_MD.read_text(encoding="utf-8")

    summary_headings = re.findall(r"^### Step (\d+): Report summary", text, re.MULTILINE)
    assert summary_headings, "no '### Step N: Report summary' heading found in SKILL.md"
    actual_summary_step = summary_headings[0]

    reference_match = re.search(r"for Step (\d+)'s summary", text)
    assert reference_match, "no \"for Step N's summary\" cross-reference found in SKILL.md"
    referenced_step = reference_match.group(1)

    assert referenced_step == actual_summary_step, (
        f"Step 3's cross-reference points to Step {referenced_step}'s summary, "
        f"but the actual summary section is Step {actual_summary_step}"
    )

    # REQ-12 pins the actual step number itself (not just internal
    # self-consistency) — the dynamic comparison above would stay green even
    # if both the heading and the cross-reference drifted together to the
    # same wrong number, which is exactly what happened once already
    # (S-12/S12: both stuck at "Step 11" after the Step-11 "Install workflow
    # scripts" insertion was reverted). Pin the exact strings so a future
    # regression to Step 11 fails even if self-consistent.
    assert "### Step 12: Report summary" in text, (
        "expected the literal heading '### Step 12: Report summary' in "
        "SKILL.md (REQ-12) — got a differently-numbered summary heading"
    )
    assert "for Step 12's summary" in text, (
        "expected the literal cross-reference \"for Step 12's summary\" in "
        "SKILL.md (REQ-12) — got a differently-numbered cross-reference"
    )
