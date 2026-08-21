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


AGENTS_DIR = REPO_ROOT / "agents"


def _agent_role_names_from_glob():
    """Return the set of role names (filename stem) under agents/*.md."""
    return {p.stem for p in AGENTS_DIR.glob("*.md")}


def _agent_role_names_from_skill_step3(text):
    """Extract the role names listed in SKILL.md's Step 3 install list
    ("install the N agent role definitions" followed by a `- <name>.md`
    bullet block)."""
    step3_match = re.search(
        r"install the \d+ agent role definitions.*?\n((?:- [a-z0-9-]+\.md\n)+)",
        text,
        re.DOTALL,
    )
    assert step3_match, (
        "no Step 3 'install the N agent role definitions' bullet list found "
        "in SKILL.md"
    )
    return set(re.findall(r"- ([a-z0-9-]+)\.md", step3_match.group(1)))


def test_skill_step3_install_list_matches_agents_dir_glob_exactly():
    """Guard test binding the hand-maintained Step 3 install list to the
    real agents/ directory.

    GIVEN `skills/tlor-init/SKILL.md` Step 3 hand-lists every agent role file
      it installs
    WHEN comparing that list against the actual `agents/*.md` glob
    THEN every name in the glob SHALL appear in the list and vice versa —
      an added, removed, or renamed agent file that isn't mirrored in
      SKILL.md would otherwise install a stale or incomplete set silently.
    """
    glob_names = _agent_role_names_from_glob()
    skill_names = _agent_role_names_from_skill_step3(SKILL_MD.read_text(encoding="utf-8"))

    assert skill_names == glob_names, (
        f"SKILL.md Step 3 install list {sorted(skill_names)} does not match "
        f"the agents/*.md glob {sorted(glob_names)} exactly"
    )


def test_skill_step3_agent_count_word_matches_agents_dir_glob_count():
    """Guard test binding Step 3's literal count word to the agents/ glob.

    GIVEN SKILL.md's "install the N agent role definitions" sentence states
      a literal count
    WHEN comparing N against `len(agents/*.md)`
    THEN they SHALL be equal — a hand-edited count that drifts from the real
      file count would otherwise go unnoticed.
    """
    glob_count = len(_agent_role_names_from_glob())
    text = SKILL_MD.read_text(encoding="utf-8")

    count_match = re.search(r"install the (\d+) agent role definitions", text)
    assert count_match, (
        "no 'install the N agent role definitions' sentence found in SKILL.md"
    )

    assert int(count_match.group(1)) == glob_count, (
        f"SKILL.md states {count_match.group(1)} agent role definitions but "
        f"the agents/*.md glob has {glob_count}"
    )


# --- M2-M6 token-reduction batch (RED phase — implementation lands later) --
#
# Both tests below target doc text that does not exist yet in the checked-in
# SKILL.md files (verified by grep before writing these: neither "merge"
# near "same test-file" wording, nor `resumeFromRunId`/`inputsHash`/a
# quota-vs-fan-out phrase, currently appears anywhere in either file) — the
# implementing dispatch adds the prose these regexes look for; these tests
# are expected to FAIL against the current source.

MODULE_CONVERGENCE_RE = re.compile(
    r"same test-file.{0,200}?merge|merge.{0,200}?same test-file",
    re.IGNORECASE | re.DOTALL,
)


def test_stdd_plan_skill_states_the_module_convergence_rule():
    """M4-doc (token-reduction M4).

    GIVEN stdd-skills/stdd-plan/SKILL.md's tasks.md-generation guidance
    WHEN reading its full text
    THEN it SHALL state that scenarios sharing the same test-file SHOULD be
      merged into one task — tolerant of exact wording, but specific enough
      that a match cannot be an accident (both "same test-file" and "merge"
      must appear within a short window of each other).
    """
    text = PLAN_SKILL.read_text(encoding="utf-8")
    assert MODULE_CONVERGENCE_RE.search(text), (
        "stdd-plan/SKILL.md does not state the module-convergence rule "
        "(scenarios sharing the same test-file SHOULD be merged into one "
        "task) anywhere in its text"
    )


QUOTA_NEAR_FAN_OUT_RE = re.compile(
    r"(quota|rate.?limit).{0,150}?fan-out|fan-out.{0,150}?(quota|rate.?limit)",
    re.IGNORECASE | re.DOTALL,
)


def test_stdd_execute_skill_documents_resume_hash_and_quota_precheck():
    """M3b/M6-doc (token-reduction M3b, M6).

    GIVEN stdd-skills/stdd-execute/SKILL.md
    WHEN reading its full text
    THEN it SHALL contain the literal identifiers `resumeFromRunId` and
      `inputsHash` (M3b: resumable, hash-addressed runs), AND SHALL document
      a quota/rate-limit pre-check performed before fanning out scenario
      tasks (M6).
    """
    text = EXECUTE_SKILL.read_text(encoding="utf-8")

    assert "resumeFromRunId" in text, (
        "stdd-execute/SKILL.md does not mention the literal identifier "
        "'resumeFromRunId' anywhere"
    )
    assert "inputsHash" in text, (
        "stdd-execute/SKILL.md does not mention the literal identifier "
        "'inputsHash' anywhere"
    )
    assert QUOTA_NEAR_FAN_OUT_RE.search(text), (
        "stdd-execute/SKILL.md does not document a quota/rate-limit "
        "pre-check performed before fanning out scenario tasks"
    )


# --- M1 batch (GWT/design inlining + M4 merged-task id token — RED phase,
# implementation lands later) ------------------------------------------------
#
# The module-convergence rule (stdd-plan/SKILL.md's existing "same test-file
# SHOULD be merged into one task" sentence, see MODULE_CONVERGENCE_RE above)
# already tells the planner to merge scenarios sharing a test-file, but never
# says what a merged task's own `id` token looks like on the tasks.md line.
# M4 fixes that: a merged task's id is the comma-joined list of its scenario
# ids inside ONE backtick token (e.g. `` `S-03,S-04` ``) — this is what
# workflows/stdd-execute.js's loadChange step 3 reports verbatim as `task.id`,
# and what markerLineMatchesId/gwtLooksValid then key off of (see
# tests/test_stdd_execute_helpers.mjs's M4 test). Verified by grep before
# writing these: neither templates/tasks.md nor SKILL.md currently contains a
# comma-joined id inside a single backtick token, or a sentence describing
# that format — these tests are expected to FAIL against the current source.

TASKS_TEMPLATE = REPO_ROOT / "stdd-skills" / "stdd-plan" / "templates" / "tasks.md"

MERGED_ID_BACKTICK_TOKEN_RE = re.compile(r"`[A-Za-z0-9._-]+,[A-Za-z0-9._-]+`")


def test_tasks_template_shows_a_merged_task_comma_id_example():
    """M4-doc (M1 batch): templates/tasks.md worked example includes a
    merged-task id.

    GIVEN stdd-skills/stdd-plan/templates/tasks.md, the worked example
      SKILL.md's module-convergence rule points readers at
    WHEN reading its full text
    THEN it SHALL contain at least one task line whose id is a single
      backtick token joining two (or more) scenario ids with a comma (e.g.
      `` `S-03,S-04` ``), demonstrating the merged-task id format.
    """
    text = TASKS_TEMPLATE.read_text(encoding="utf-8")
    assert MERGED_ID_BACKTICK_TOKEN_RE.search(text), (
        "stdd-skills/stdd-plan/templates/tasks.md does not contain a merged-"
        "task example line (a single backtick token joining two scenario "
        "ids with a comma, e.g. `S-03,S-04`)"
    )


MERGED_TASK_ID_FORMAT_RE = re.compile(
    r"\bcomma\b.{0,150}?\b(id|backtick)\b|\b(id|backtick)\b.{0,150}?\bcomma\b",
    re.IGNORECASE | re.DOTALL,
)


EN_INSTALLATION_DOC = REPO_ROOT / "docs" / "en" / "installation.md"
ZH_INSTALLATION_DOC = REPO_ROOT / "docs" / "zh-TW" / "installation.md"
INSTALL_SH = REPO_ROOT / "install.sh"


def _flag_literals_from_install_sh_arg_case_block():
    """Extract every flag literal (e.g. `--force`, `--stdd-role=`) from
    install.sh's argument-parsing `case "$a" in ... esac` block, excluding
    the catch-all `*)` fallback branch. `--stdd-role=*` is trimmed to
    `--stdd-role=` since that trailing `*` is a shell glob, not doc text."""
    text = INSTALL_SH.read_text(encoding="utf-8")
    block_match = re.search(r'case "\$a" in(.*?)\n\s*esac', text, re.DOTALL)
    assert block_match, (
        'install.sh: could not find the argument-parsing `case "$a" in ... '
        "esac` block"
    )
    flags = []
    for line in block_match.group(1).splitlines():
        line = line.strip()
        m = re.match(r"(--[\w=*-]+)\)", line)
        if not m:
            continue
        token = m.group(1)
        if token == "*":
            continue
        flags.append(token.rstrip("*"))
    return flags


def test_every_install_sh_flag_literal_is_documented_in_both_language_docs():
    """Guard test binding install.sh's recognized flags to the installation
    docs.

    GIVEN install.sh's argument-parsing `case` block (install.sh:51-59) lists
      every flag the script recognizes
    WHEN comparing each flag literal against `docs/en/installation.md` and
      `docs/zh-TW/installation.md`
    THEN every flag SHALL appear in BOTH docs — an added flag (e.g. a future
      `--skills-dest=PATH`) that isn't documented in both languages would
      otherwise go unnoticed.
    """
    flags = _flag_literals_from_install_sh_arg_case_block()
    assert flags, "no flag literals extracted from install.sh's case block"

    en_text = EN_INSTALLATION_DOC.read_text(encoding="utf-8")
    zh_text = ZH_INSTALLATION_DOC.read_text(encoding="utf-8")

    for flag in flags:
        assert flag in en_text, (
            f"{flag!r} (from install.sh's argument-parsing case block) is "
            "missing from docs/en/installation.md"
        )
        assert flag in zh_text, (
            f"{flag!r} (from install.sh's argument-parsing case block) is "
            "missing from docs/zh-TW/installation.md"
        )


BILBO_SCRIBE_MD = REPO_ROOT / "agent_doc" / "bilbo-scribe.md"

AGENT_DOC_PATH_RE = re.compile(r"agent_doc/[\w./\-]+\.md")


def _routing_table_also_read_paths(text):
    """Extract every `agent_doc/...md` path referenced in bilbo-scribe.md's
    '## Routing table' section's 'Also Read' column. Parses whatever rows
    the table contains at test time (no hardcoded row list), so a future
    added row is covered automatically."""
    table_match = re.search(
        r"## Routing table\n\n(.*?)\n\n", text, re.DOTALL
    )
    assert table_match, (
        "bilbo-scribe.md: could not find the '## Routing table' section"
    )
    table_text = table_match.group(1)
    return set(AGENT_DOC_PATH_RE.findall(table_text))


def test_bilbo_scribe_routing_table_paths_all_exist():
    """Guard test binding bilbo-scribe.md's routing table to the real
    agent_doc/ directory.

    GIVEN bilbo-scribe.md's '## Routing table' lists `agent_doc/...md`
      paths a role should Read for each condition
    WHEN parsing every such path out of the table dynamically (not a
      hardcoded list)
    THEN every path SHALL exist under the repo's `agent_doc/` — a row
      added later that names a doc which was never written (or was
      renamed/removed) would otherwise go unnoticed.
    """
    text = BILBO_SCRIBE_MD.read_text(encoding="utf-8")
    paths = _routing_table_also_read_paths(text)
    assert paths, "no 'agent_doc/...md' paths found in the routing table"

    missing = sorted(p for p in paths if not (REPO_ROOT / p).is_file())
    assert not missing, (
        f"bilbo-scribe.md routing table references paths that do not exist "
        f"in the repo: {missing}"
    )


def test_stdd_plan_skill_states_the_merged_task_id_line_format():
    """M4-doc (M1 batch): stdd-plan/SKILL.md documents the merged-task id
    line format.

    GIVEN stdd-skills/stdd-plan/SKILL.md's module-convergence rule (scenarios
      sharing a test-file SHOULD be merged into one task)
    WHEN reading its full text
    THEN it SHALL also state HOW a merged task's id is written on the
      tasks.md line — a single backtick token joining the merged scenario
      ids with a comma — tolerant of exact wording, but specific enough that
      a match cannot be an accident ("comma" and "id"/"backtick" must appear
      within a short window of each other).
    """
    text = PLAN_SKILL.read_text(encoding="utf-8")
    assert MERGED_TASK_ID_FORMAT_RE.search(text), (
        "stdd-plan/SKILL.md does not state the merged-task id line format "
        "(a single backtick token joining the merged scenario ids with a "
        "comma) anywhere in its text"
    )
