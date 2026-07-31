# -*- coding: utf-8 -*-
"""Black-box tests for hooks/stdd_test_guard.py."""
import pytest

from conftest import HOOKS_DIR

SCRIPT = HOOKS_DIR / "stdd_test_guard.py"

TASKS_MD = """\
- [wip] Implement feature X
  Test file: `tests/test_wip_thing.py`

- [ ] Implement feature Y
  Test file: `tests/test_other_thing.py`
"""


def _payload(file_path, cwd, tool_name="Edit"):
    return {
        "tool_name": tool_name,
        "tool_input": {"file_path": file_path},
        "cwd": cwd,
    }


def _make_tasks_md(tmp_path):
    change_dir = tmp_path / "STDD" / "some-change"
    change_dir.mkdir(parents=True)
    tasks_md = change_dir / "tasks.md"
    tasks_md.write_text(TASKS_MD, encoding="utf-8")
    return tmp_path


def test_wip_test_file_is_denied(run_hook, tmp_path):
    cwd = _make_tasks_md(tmp_path)
    result = run_hook(
        SCRIPT,
        _payload(str(cwd / "tests" / "test_wip_thing.py"), str(cwd)),
    )
    assert result.returncode == 0
    decision = result.decision
    assert decision is not None
    assert decision["hookSpecificOutput"]["permissionDecision"] == "deny"


def test_non_wip_test_file_is_allowed(run_hook, tmp_path):
    cwd = _make_tasks_md(tmp_path)
    result = run_hook(
        SCRIPT,
        _payload(str(cwd / "tests" / "test_other_thing.py"), str(cwd)),
    )
    assert result.returncode == 0
    assert result.decision is None


def test_allow_test_rewrite_env_bypasses_deny(run_hook, tmp_path):
    cwd = _make_tasks_md(tmp_path)
    result = run_hook(
        SCRIPT,
        _payload(str(cwd / "tests" / "test_wip_thing.py"), str(cwd)),
        env_overrides={"TLOR_STDD_ALLOW_TEST_REWRITE": "1"},
    )
    assert result.returncode == 0
    assert result.decision is None


def test_no_tasks_md_allows(run_hook, tmp_path):
    result = run_hook(
        SCRIPT,
        _payload(str(tmp_path / "tests" / "test_wip_thing.py"), str(tmp_path)),
    )
    assert result.returncode == 0
    assert result.decision is None


def test_malformed_stdin_fails_open(run_hook, tmp_path):
    result = run_hook(
        SCRIPT,
        "not json",
        cwd=str(tmp_path),
    )
    assert result.returncode == 0
    assert result.decision is None


def _make_specs_name_tasks_md(tmp_path):
    change_dir = tmp_path / "specs" / "some-change"
    change_dir.mkdir(parents=True)
    tasks_md = change_dir / "tasks.md"
    tasks_md.write_text(TASKS_MD, encoding="utf-8")
    return tmp_path


def test_specs_name_layout_tasks_md_is_recognised_and_protects_wip_test_file(run_hook, tmp_path):
    cwd = _make_specs_name_tasks_md(tmp_path)
    result = run_hook(
        SCRIPT,
        _payload(str(cwd / "tests" / "test_wip_thing.py"), str(cwd)),
    )
    assert result.returncode == 0
    decision = result.decision
    assert decision is not None
    assert decision["hookSpecificOutput"]["permissionDecision"] == "deny"


def test_wip_test_file_reference_does_not_protect_the_implementation_file(run_hook, tmp_path):
    """A [wip] task citing `tests/test_wip_thing.py` must NOT deny a write to
    the module under test (e.g. `src/wip_thing.py`) — the reverse
    `candidate.endswith(basename)` match wrongly treated any file whose
    basename is a suffix of the cited test path as protected, deadlocking
    the GREEN dispatch's implementation write for the whole [wip] window."""
    cwd = _make_tasks_md(tmp_path)
    result = run_hook(
        SCRIPT,
        _payload(str(cwd / "src" / "wip_thing.py"), str(cwd)),
    )
    assert result.returncode == 0
    assert result.decision is None


def test_wip_test_file_itself_is_still_denied_at_a_deeper_path(run_hook, tmp_path):
    """Companion to the above: protection of the cited test file itself must
    be preserved even when file_path is a longer, /-aligned path than the
    cited candidate (e.g. an absolute path ending in the candidate)."""
    cwd = _make_tasks_md(tmp_path)
    result = run_hook(
        SCRIPT,
        _payload(str(cwd / "tests" / "test_wip_thing.py"), str(cwd)),
    )
    assert result.returncode == 0
    decision = result.decision
    assert decision is not None
    assert decision["hookSpecificOutput"]["permissionDecision"] == "deny"


DOTSLASH_TASKS_MD = """\
- [wip] Implement feature X
  Test file: `./tests/test_wip_thing.py`
"""


def test_dotslash_prefixed_citation_still_denies_the_real_test_file(run_hook, tmp_path):
    """A `./`-prefixed citation must resolve to the same file as the
    unprefixed real path — pure text `_same_file` comparison used to treat
    `/repo/tests/test_foo.py` vs `./tests/test_foo.py` as different files,
    giving zero protection to a task written with a `./` prefix."""
    change_dir = tmp_path / "STDD" / "some-change"
    change_dir.mkdir(parents=True)
    (change_dir / "tasks.md").write_text(DOTSLASH_TASKS_MD, encoding="utf-8")

    result = run_hook(
        SCRIPT,
        _payload(str(tmp_path / "tests" / "test_wip_thing.py"), str(tmp_path)),
    )
    assert result.returncode == 0
    decision = result.decision
    assert decision is not None
    assert decision["hookSpecificOutput"]["permissionDecision"] == "deny"


def test_same_named_file_outside_root_is_not_denied(run_hook, tmp_path):
    """A file with the same name/suffix but living entirely OUTSIDE the tree
    this guard scanned (cwd/root) must never be denied — suffix-only
    matching was not anchored to the project root."""
    cwd = _make_tasks_md(tmp_path)
    outside_file = tmp_path.parent / "unrelated-project" / "tests" / "test_wip_thing.py"
    result = run_hook(
        SCRIPT,
        _payload(str(outside_file), str(cwd)),
    )
    assert result.returncode == 0
    assert result.decision is None


FUNCTION_NAME_TASKS_MD = """\
- [wip] Implement feature X
  Covers: `test_login`
"""


TEMPLATE_CITATION_TASKS_MD = """\
- [wip] `S-01` `[NEW]` Retry scheduling on 5xx response
  - RED: write `tests/webhook/test_retry_scheduling.py::test_5xx_schedules_retry`
    asserting a retry is enqueued with the correct backoff delay
"""


def test_template_shaped_citation_with_test_name_suffix_denies_real_file(run_hook, tmp_path):
    """The framework's own canonical citation shape (tasks.md template
    :16/:33) attaches `::test_name` to the path — a bare-string comparison
    against the real file_path (which never carries that suffix) can never
    be equal, silently disabling the guard on every template-conformant
    tasks.md."""
    change_dir = tmp_path / "STDD" / "some-change"
    change_dir.mkdir(parents=True)
    (change_dir / "tasks.md").write_text(TEMPLATE_CITATION_TASKS_MD, encoding="utf-8")
    test_file = tmp_path / "tests" / "webhook" / "test_retry_scheduling.py"
    test_file.parent.mkdir(parents=True)
    test_file.write_text("def test_5xx_schedules_retry():\n    pass\n", encoding="utf-8")

    result = run_hook(
        SCRIPT,
        _payload(str(test_file), str(tmp_path)),
    )
    assert result.returncode == 0
    decision = result.decision
    assert decision is not None
    assert decision["hookSpecificOutput"]["permissionDecision"] == "deny"


def test_symlinked_path_component_still_denies_real_protected_file(run_hook, tmp_path):
    """A symlinked directory component (e.g. macOS /tmp -> /private/tmp, a
    symlinked worktree/home) must not defeat the comparison: cwd is reported
    through the symlink alias, but the write's file_path arrives already
    resolved to the real path (as Claude Code's own path normalization can
    do) — normpath alone never resolves symlinks, so the two never compare
    equal without realpath on both sides."""
    real_root = tmp_path / "real_root"
    real_root.mkdir()
    change_dir = real_root / "STDD" / "some-change"
    change_dir.mkdir(parents=True)
    (change_dir / "tasks.md").write_text(TASKS_MD, encoding="utf-8")
    (real_root / "tests").mkdir()
    (real_root / "tests" / "test_wip_thing.py").write_text("pass\n", encoding="utf-8")

    symlink_root = tmp_path / "alias_root"
    try:
        symlink_root.symlink_to(real_root, target_is_directory=True)
    except OSError:
        pytest.skip("symlinks not supported on this filesystem")

    result = run_hook(
        SCRIPT,
        _payload(str(real_root / "tests" / "test_wip_thing.py"), str(symlink_root)),
    )
    assert result.returncode == 0
    decision = result.decision
    assert decision is not None
    assert decision["hookSpecificOutput"]["permissionDecision"] == "deny"


def test_in_repo_symlink_alias_to_protected_file_is_denied(run_hook, tmp_path):
    """An in-repo symlink pointing AT the protected file must still be
    treated as a write to the same inode, not a different, unprotected
    file."""
    cwd = _make_tasks_md(tmp_path)
    (cwd / "tests").mkdir()
    real_test_file = cwd / "tests" / "test_wip_thing.py"
    real_test_file.write_text("pass\n", encoding="utf-8")
    alias = cwd / "tests" / "test_wip_thing_alias.py"
    try:
        alias.symlink_to(real_test_file)
    except OSError:
        pytest.skip("symlinks not supported on this filesystem")

    result = run_hook(
        SCRIPT,
        _payload(str(alias), str(cwd)),
    )
    assert result.returncode == 0
    decision = result.decision
    assert decision is not None
    assert decision["hookSpecificOutput"]["permissionDecision"] == "deny"


def _fs_is_case_insensitive(tmp_path):
    probe_lower = tmp_path / "case_probe.txt"
    probe_lower.write_text("x", encoding="utf-8")
    probe_upper = tmp_path / "CASE_PROBE.txt"
    return probe_upper.exists()


def test_case_variant_citation_denies_on_case_insensitive_fs(run_hook, tmp_path):
    """On a case-insensitive filesystem, `tests/TEST_wip_thing.py` and the
    cited `tests/test_wip_thing.py` are the SAME inode — normpath-only
    comparison (case-sensitive string equality) wrongly allowed the write.
    Detected, not assumed: skipped on a case-sensitive filesystem."""
    if not _fs_is_case_insensitive(tmp_path):
        pytest.skip("filesystem is case-sensitive")
    cwd = _make_tasks_md(tmp_path)
    (cwd / "tests").mkdir()
    real_test_file = cwd / "tests" / "test_wip_thing.py"
    real_test_file.write_text("pass\n", encoding="utf-8")

    result = run_hook(
        SCRIPT,
        _payload(str(cwd / "tests" / "TEST_wip_thing.py"), str(cwd)),
    )
    assert result.returncode == 0
    decision = result.decision
    assert decision is not None
    assert decision["hookSpecificOutput"]["permissionDecision"] == "deny"


def test_cited_function_name_does_not_protect_anything(run_hook, tmp_path):
    """A backticked span that names a test FUNCTION (no `/`, no source
    extension) must not be treated as a protected path at all — it isn't a
    citation of the test file, and matching against it as if it were a path
    could deny unrelated writes."""
    change_dir = tmp_path / "STDD" / "some-change"
    change_dir.mkdir(parents=True)
    (change_dir / "tasks.md").write_text(FUNCTION_NAME_TASKS_MD, encoding="utf-8")

    result = run_hook(
        SCRIPT,
        _payload(str(tmp_path / "test_login"), str(tmp_path)),
    )
    assert result.returncode == 0
    assert result.decision is None
