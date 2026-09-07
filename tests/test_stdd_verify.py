# -*- coding: utf-8 -*-
"""Tests for scripts/stdd_verify.py.

Module functions (parse_scenarios, run_scenario, mapped_test_file) are
imported directly for the scenario-level behavior; main()/CLI-argument
behavior (filtering, unknown-scenario exit code) is driven as a subprocess,
matching this repo's black-box convention for the CLI surface while still
avoiding a full subprocess round-trip for every scenario case.
"""
import subprocess
import sys

sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent.parent / "scripts"))

from conftest import REPO_ROOT
import stdd_verify

SCRIPT = REPO_ROOT / "scripts" / "stdd_verify.py"

PY = sys.executable


def spec_text(scenarios):
    """Build a minimal spec.md body from a list of
    (id, title, test_mapping, verification_command) tuples. Uses the exact
    template field syntax (spec.md:95-96): `#### S-XX: <title>` heading,
    then GWT, then the two `**field**: \\`value\\`` lines."""
    parts = ["# Spec: Toy\n\n## Capability: Toy\n"]
    for sid, title, mapping, command in scenarios:
        block = [f"#### {sid}: {title}\n"]
        block.append("- **GIVEN** a thing\n- **WHEN** it happens\n- **THEN** it works\n")
        if mapping is not None:
            block.append(f"**Test mapping**: `{mapping}`\n")
        if command is not None:
            block.append(f"**Verification command**: `{command}`\n")
        parts.append("\n".join(block) + "\n")
    return "\n".join(parts)


def write_spec(tmp_path, scenarios, name="spec.md"):
    path = tmp_path / name
    path.write_text(spec_text(scenarios), encoding="utf-8")
    return path


def run_cli(args):
    return subprocess.run(
        [PY, str(SCRIPT)] + args, capture_output=True, text=True
    )


# --------------------------------------------------------------------------
# parse_scenarios / mapped_test_file (direct import)
# --------------------------------------------------------------------------

def test_parse_scenarios_extracts_id_mapping_and_command(tmp_path):
    path = write_spec(
        tmp_path,
        [("S-01", "does a thing", "tests/toy/test_x.py::test_ok", f"{PY} -c \"import sys; sys.exit(0)\"")],
    )
    scenarios = stdd_verify.parse_scenarios(path.read_text(encoding="utf-8"))
    assert len(scenarios) == 1
    assert scenarios[0]["id"] == "S-01"
    assert scenarios[0]["test_mapping"] == "tests/toy/test_x.py::test_ok"
    assert scenarios[0]["verification_command"] == f'{PY} -c "import sys; sys.exit(0)"'


def test_mapped_test_file_splits_on_double_colon():
    assert stdd_verify.mapped_test_file("tests/x.py::test_ok") == "tests/x.py"
    assert stdd_verify.mapped_test_file("tests/x.py") == "tests/x.py"
    assert stdd_verify.mapped_test_file("") is None


# --------------------------------------------------------------------------
# (1) all-PASS
# --------------------------------------------------------------------------

def test_all_pass_scenarios_exit_zero_with_coverage_line(tmp_path):
    test_file = tmp_path / "tests" / "toy" / "test_x.py"
    test_file.parent.mkdir(parents=True)
    test_file.write_text("def test_ok(): pass\n", encoding="utf-8")
    spec_path = write_spec(
        tmp_path,
        [
            ("S-01", "first", "tests/toy/test_x.py::test_ok", f"{PY} -c \"import sys; sys.exit(0)\""),
            ("S-02", "second", "tests/toy/test_x.py::test_ok", f"{PY} -c \"import sys; sys.exit(0)\""),
        ],
    )
    proc = run_cli(["--spec", str(spec_path), "--root", str(tmp_path)])
    assert proc.returncode == 0, proc.stdout + proc.stderr
    lines = proc.stdout.splitlines()
    assert lines[0].startswith("S-01  PASS  "), lines[0]
    assert lines[1].startswith("S-02  PASS  "), lines[1]
    assert lines[2] == "Coverage: 2/2 scenarios green", lines[2]


# --------------------------------------------------------------------------
# (2) one FAIL
# --------------------------------------------------------------------------

def test_one_failing_scenario_exits_nonzero_and_reports_fail_row(tmp_path):
    test_file = tmp_path / "tests" / "toy" / "test_x.py"
    test_file.parent.mkdir(parents=True)
    test_file.write_text("def test_ok(): pass\n", encoding="utf-8")
    spec_path = write_spec(
        tmp_path,
        [
            ("S-01", "first", "tests/toy/test_x.py::test_ok", f"{PY} -c \"import sys; sys.exit(0)\""),
            ("S-02", "second", "tests/toy/test_x.py::test_ok", f"{PY} -c \"import sys; sys.exit(1)\""),
        ],
    )
    proc = run_cli(["--spec", str(spec_path), "--root", str(tmp_path)])
    assert proc.returncode == 1, proc.stdout + proc.stderr
    lines = proc.stdout.splitlines()
    assert lines[0].startswith("S-01  PASS  ")
    assert lines[1].startswith("S-02  FAIL  ")
    assert lines[2] == "Coverage: 1/2 scenarios green"


# --------------------------------------------------------------------------
# (3) MISSING — absent field, or mapped test file absent
# --------------------------------------------------------------------------

def test_missing_verification_command_field_is_missing_not_a_crash(tmp_path):
    test_file = tmp_path / "tests" / "toy" / "test_x.py"
    test_file.parent.mkdir(parents=True)
    test_file.write_text("def test_ok(): pass\n", encoding="utf-8")
    spec_path = write_spec(
        tmp_path,
        [("S-01", "first", "tests/toy/test_x.py::test_ok", None)],
    )
    proc = run_cli(["--spec", str(spec_path), "--root", str(tmp_path)])
    assert proc.returncode == 1, proc.stdout + proc.stderr
    lines = proc.stdout.splitlines()
    assert lines[0].startswith("S-01  MISSING  ")
    assert lines[1] == "Coverage: 0/1 scenarios green"


def test_mapped_test_file_not_existing_is_missing(tmp_path):
    spec_path = write_spec(
        tmp_path,
        [("S-01", "first", "tests/toy/test_nope.py::test_ok", f"{PY} -c \"import sys; sys.exit(0)\"")],
    )
    proc = run_cli(["--spec", str(spec_path), "--root", str(tmp_path)])
    assert proc.returncode == 1, proc.stdout + proc.stderr
    lines = proc.stdout.splitlines()
    assert lines[0].startswith("S-01  MISSING  ")


def test_missing_test_mapping_field_is_also_missing(tmp_path):
    spec_path = write_spec(
        tmp_path,
        [("S-01", "first", None, f"{PY} -c \"import sys; sys.exit(0)\"")],
    )
    proc = run_cli(["--spec", str(spec_path), "--root", str(tmp_path)])
    assert proc.returncode == 1, proc.stdout + proc.stderr
    lines = proc.stdout.splitlines()
    assert lines[0].startswith("S-01  MISSING  ")


# --------------------------------------------------------------------------
# (4) --scenario filter
# --------------------------------------------------------------------------

def test_scenario_filter_selects_only_the_named_subset(tmp_path):
    test_file = tmp_path / "tests" / "toy" / "test_x.py"
    test_file.parent.mkdir(parents=True)
    test_file.write_text("def test_ok(): pass\n", encoding="utf-8")
    spec_path = write_spec(
        tmp_path,
        [
            ("S-01", "first", "tests/toy/test_x.py::test_ok", f"{PY} -c \"import sys; sys.exit(0)\""),
            ("S-02", "second", "tests/toy/test_x.py::test_ok", f"{PY} -c \"import sys; sys.exit(1)\""),
        ],
    )
    proc = run_cli(["--spec", str(spec_path), "--root", str(tmp_path), "--scenario", "S-01"])
    assert proc.returncode == 0, proc.stdout + proc.stderr
    lines = proc.stdout.splitlines()
    assert len(lines) == 2
    assert lines[0].startswith("S-01  PASS  ")
    assert lines[1] == "Coverage: 1/1 scenarios green"


def test_scenario_filter_is_repeatable(tmp_path):
    test_file = tmp_path / "tests" / "toy" / "test_x.py"
    test_file.parent.mkdir(parents=True)
    test_file.write_text("def test_ok(): pass\n", encoding="utf-8")
    spec_path = write_spec(
        tmp_path,
        [
            ("S-01", "first", "tests/toy/test_x.py::test_ok", f"{PY} -c \"import sys; sys.exit(0)\""),
            ("S-02", "second", "tests/toy/test_x.py::test_ok", f"{PY} -c \"import sys; sys.exit(0)\""),
            ("S-03", "third", "tests/toy/test_x.py::test_ok", f"{PY} -c \"import sys; sys.exit(1)\""),
        ],
    )
    proc = run_cli(
        [
            "--spec", str(spec_path), "--root", str(tmp_path),
            "--scenario", "S-01", "--scenario", "S-03",
        ]
    )
    assert proc.returncode == 1, proc.stdout + proc.stderr
    lines = proc.stdout.splitlines()
    assert [l.split()[0] for l in lines[:-1]] == ["S-01", "S-03"]
    assert lines[-1] == "Coverage: 1/2 scenarios green"


# --------------------------------------------------------------------------
# (5) unknown --scenario id
# --------------------------------------------------------------------------

def test_unknown_scenario_id_errors_with_exit_2(tmp_path):
    spec_path = write_spec(
        tmp_path,
        [("S-01", "first", "tests/toy/test_x.py::test_ok", f"{PY} -c \"import sys; sys.exit(0)\"")],
    )
    proc = run_cli(["--spec", str(spec_path), "--root", str(tmp_path), "--scenario", "S-99"])
    assert proc.returncode == 2, proc.stdout + proc.stderr
    assert "S-99" in proc.stderr
    assert proc.stdout == ""


# --------------------------------------------------------------------------
# --change convenience flag
# --------------------------------------------------------------------------

def test_change_flag_is_equivalent_to_spec_dir_spec_md(tmp_path):
    change_dir = tmp_path / "STDD" / "toy-change"
    change_dir.mkdir(parents=True)
    write_spec(
        change_dir,
        [("S-01", "first", "tests/toy/test_x.py::test_ok", f"{PY} -c \"import sys; sys.exit(0)\"")],
    )
    proc = run_cli(["--change", str(change_dir), "--root", str(tmp_path)])
    assert proc.returncode == 1, proc.stdout + proc.stderr  # mapped test file doesn't exist -> MISSING
    lines = proc.stdout.splitlines()
    assert lines[0].startswith("S-01  MISSING  ")


def test_spec_and_change_together_is_a_usage_error(tmp_path):
    spec_path = write_spec(
        tmp_path,
        [("S-01", "first", "tests/toy/test_x.py::test_ok", f"{PY} -c \"import sys; sys.exit(0)\"")],
    )
    proc = run_cli(["--spec", str(spec_path), "--change", str(tmp_path)])
    assert proc.returncode == 2, proc.stdout + proc.stderr


def test_missing_spec_file_is_reported_and_exits_2(tmp_path):
    proc = run_cli(["--spec", str(tmp_path / "nope.md")])
    assert proc.returncode == 2
    assert "nope.md" in proc.stderr


def test_neither_spec_nor_change_is_a_usage_error():
    proc = run_cli([])
    assert proc.returncode == 2
