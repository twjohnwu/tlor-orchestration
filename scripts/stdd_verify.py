#!/usr/bin/env python3
"""Run every scenario's Verification command in an STDD spec.md and report a
per-scenario PASS/FAIL/MISSING verdict, plus an overall coverage line.

Why this exists: spec.md already carries a `Test mapping` and a
`Verification command` field per scenario (framework template:
stdd-skills/stdd-spec/templates/spec.md:95-96 — the exact field syntax this
script parses, `**Test mapping**: \\`...\\`` / `**Verification command**:
\\`...\\``, one per S-XX scenario, immediately following its GWT block), but
nothing runs them as a SET and reports scenario-level results. This script
is that runner, so the spec becomes living executable documentation instead
of prose a reviewer has to run by hand, one command at a time.

Scenario blocks are found by the SAME `#### S-XX:` heading level the
template uses (spec.md:85/98) and bounded by the next heading of any level
(so a scenario's block never bleeds into `## Rejected options` etc., see
spec.md:109).

`--root`: the working directory verification commands run in. Default is
the CURRENT directory (`.`), not an auto-detected repository root — this
script does not try to guess a project root from the spec path (e.g. by
walking up for a `.git`/`STDD` marker), since a spec can live at more than
one depth relative to where its `Verification command` paths are meant to
resolve. Pass `--root` explicitly when the spec's commands assume a
directory other than cwd.

A scenario is MISSING (not a crash, not a FAIL) when either its
`Verification command` field is absent/empty, or the test file its `Test
mapping` field names does not exist on disk (mapping without a `::` marker
is itself the whole file path; with one, the part before `::` is the file).
A scenario whose `Test mapping` field is itself absent/empty is also treated
as MISSING (there is no mapped file to confirm exists) — this is a local
judgment call, not a case the framework docs spell out explicitly.

Exit status: 0 iff every SELECTED scenario is PASS, 1 otherwise (a MISSING
counts as not green). Requesting an unknown `--scenario` id is a usage
error: exit 2, no report printed. This program is otherwise read-only aside
from the side effects of whatever verification commands it invokes.
"""
import argparse
import re
import subprocess
import sys
from pathlib import Path

# Any markdown heading line, any level — used only to find each scenario
# block's boundary (the next heading of ANY level ends the current one).
HEADING_RE = re.compile(r"^(#+)\s+(.*)$", re.MULTILINE)

# The template's own scenario heading: `#### S-01: A 5xx response ...`
# (stdd-skills/stdd-spec/templates/spec.md:85).
SCENARIO_HEADING_RE = re.compile(r"^####\s+(S-\d+):")

# Field syntax verbatim from the template (spec.md:95-96):
#   **Test mapping**: `tests/webhook/test_retry_scheduling.py::test_...`
#   **Verification command**: `pytest tests/webhook/test_retry_scheduling.py::test_... -q`
TEST_MAPPING_RE = re.compile(r"\*\*Test mapping\*\*:\s*`([^`]*)`")
VERIFY_CMD_RE = re.compile(r"\*\*Verification command\*\*:\s*`([^`]*)`")


def parse_scenarios(text: str) -> list:
    """Ordered list of {id, test_mapping, verification_command} dicts, one
    per `#### S-XX:` heading found in `text`, in document order."""
    headings = list(HEADING_RE.finditer(text))
    scenarios = []
    for i, heading in enumerate(headings):
        match = SCENARIO_HEADING_RE.match(heading.group(0))
        if not match:
            continue
        start = heading.end()
        end = headings[i + 1].start() if i + 1 < len(headings) else len(text)
        block = text[start:end]
        test_mapping = TEST_MAPPING_RE.search(block)
        verify_cmd = VERIFY_CMD_RE.search(block)
        scenarios.append(
            {
                "id": match.group(1),
                "test_mapping": test_mapping.group(1).strip() if test_mapping else "",
                "verification_command": verify_cmd.group(1).strip() if verify_cmd else "",
            }
        )
    return scenarios


def mapped_test_file(test_mapping: str):
    """The test FILE a `Test mapping` field names — the part before `::` if
    present, else the whole value. None if the field is empty."""
    if not test_mapping:
        return None
    return test_mapping.split("::", 1)[0].strip() or None


def run_scenario(scenario: dict, root: Path):
    """Returns (status, proc) where status is PASS/FAIL/MISSING and proc is
    the completed subprocess (None for MISSING, since nothing was run)."""
    verification_command = scenario["verification_command"]
    if not verification_command:
        return "MISSING", None
    test_file = mapped_test_file(scenario["test_mapping"])
    if test_file is None or not (root / test_file).is_file():
        return "MISSING", None
    proc = subprocess.run(
        verification_command, shell=True, cwd=str(root), capture_output=True, text=True
    )
    return ("PASS" if proc.returncode == 0 else "FAIL"), proc


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Run each scenario's Verification command from an STDD spec.md "
            "and report a per-scenario PASS/FAIL/MISSING verdict."
        )
    )
    parser.add_argument("--spec", default=None, help="path to a spec.md")
    parser.add_argument(
        "--change",
        default=None,
        help="a change directory; equivalent to --spec <dir>/spec.md",
    )
    parser.add_argument(
        "--scenario",
        action="append",
        default=None,
        metavar="S-XX",
        help="run only this scenario id; repeatable",
    )
    parser.add_argument(
        "--root",
        default=".",
        help="working directory verification commands run in (default: current directory)",
    )
    args = parser.parse_args(argv)

    if args.spec is not None and args.change is not None:
        parser.error("--spec and --change are mutually exclusive")
    if args.spec is None and args.change is None:
        parser.error("either --spec or --change is required")

    spec_path = Path(args.spec) if args.spec is not None else Path(args.change) / "spec.md"
    if not spec_path.is_file():
        print(f"stdd_verify.py: no spec.md at {spec_path}", file=sys.stderr)
        return 2

    root = Path(args.root)
    text = spec_path.read_text(encoding="utf-8")
    scenarios = parse_scenarios(text)
    by_id = {s["id"]: s for s in scenarios}

    if args.scenario:
        unknown = [sid for sid in args.scenario if sid not in by_id]
        if unknown:
            print(
                f"stdd_verify.py: unknown scenario id(s): {', '.join(unknown)}",
                file=sys.stderr,
            )
            return 2
        selected = [by_id[sid] for sid in args.scenario]
    else:
        selected = scenarios

    green = 0
    for scenario in selected:
        status, _ = run_scenario(scenario, root)
        if status == "PASS":
            green += 1
        print(f"{scenario['id']}  {status}  {scenario['test_mapping']}")

    print(f"Coverage: {green}/{len(selected)} scenarios green")
    return 0 if green == len(selected) else 1


if __name__ == "__main__":
    sys.exit(main())
