# -*- coding: utf-8 -*-
"""Black-box tests for install.sh's --dry-run flag: it must never create any
directory before its own dry-run early-exit check."""
import os
import shutil
import subprocess

from conftest import REPO_ROOT

INSTALL_SH = REPO_ROOT / "install.sh"


def test_dry_run_with_redirected_home_creates_zero_directories(tmp_path):
    """S-19: `HOME=<tmpdir>` 下執行 `install.sh --dry-run`，該暫存目錄底下沒有
    任何新目錄被建立 (spec.md:719-729).

    GIVEN a never-installed clean tmp dir set as HOME (no `.claude/` structure
      under it at all)
    WHEN `install.sh --dry-run` runs with that HOME
    THEN stdout SHALL contain "dry-run done (nothing written)." AND
      afterwards `<tmpdir>` SHALL NOT contain any newly created directory
      (covering all `mkdir -p` sites, now twelve after the agent_doc/
      asset type added two more at install.sh:590,600 — the original ten
      references (install.sh:373,416,421,430,441,457,466,479,500,505) had
      already drifted from actual line numbers before this change and are
      left as-is; the assertion itself is line-number-agnostic).
    """
    home = tmp_path / "home"
    home.mkdir()

    dirs_before = {p for p in _all_dirs(tmp_path)}

    env = os.environ.copy()
    env["HOME"] = str(home)
    bash_path = shutil.which("bash") or "/bin/bash"
    proc = subprocess.run(
        [bash_path, str(INSTALL_SH), "--dry-run"],
        capture_output=True,
        text=True,
        env=env,
        cwd=str(REPO_ROOT),
    )

    assert "dry-run done (nothing written)." in proc.stdout, (
        f"expected dry-run completion message in stdout, got: {proc.stdout!r} "
        f"stderr: {proc.stderr!r}"
    )

    dirs_after = {p for p in _all_dirs(tmp_path)}
    new_dirs = dirs_after - dirs_before
    assert new_dirs == set(), f"dry-run created new directories: {sorted(new_dirs)}"


def _all_dirs(root):
    for dirpath, dirnames, _filenames in os.walk(str(root)):
        for d in dirnames:
            yield os.path.join(dirpath, d)


# --- --skills-dest=PATH flag (RED phase — not yet implemented) -------------
#
# `ensure_skills_dest_safe` (install.sh:173-188) currently aborts the WHOLE
# install whenever `~/.claude/skills` is a symlink resolving outside
# `~/.claude`. The fix under test lets the user declare the skills
# destination once via `--skills-dest=PATH`, persisted to
# `~/.claude/.tlor-install.conf`, so later runs need no flag. These tests
# define that contract and are expected to FAIL against the current
# install.sh (verified: `--skills-dest=...` is not a recognized flag yet,
# so every invocation below hits the `*) echo "unknown arg: $a"` fallback at
# install.sh:58).


def _run_install(env, args):
    """Run install.sh (non-dry-run by default) with the given env/args."""
    bash_path = shutil.which("bash") or "/bin/bash"
    return subprocess.run(
        [bash_path, str(INSTALL_SH), *args],
        capture_output=True,
        text=True,
        env=env,
        cwd=str(REPO_ROOT),
    )


def _env_with_home(home):
    env = os.environ.copy()
    env["HOME"] = str(home)
    return env


def test_declared_skills_dest_installs_skills_there_and_not_at_default(tmp_path):
    """A declared `--skills-dest=<path>` installs skills under that path
    instead of the default `$HOME/.claude/skills`."""
    home = tmp_path / "home"
    home.mkdir()
    custom = tmp_path / "custom"
    env = _env_with_home(home)

    proc = _run_install(env, [f"--skills-dest={custom}", "--force"])

    assert proc.returncode == 0, (
        f"expected exit 0, got {proc.returncode}; stdout: {proc.stdout!r} "
        f"stderr: {proc.stderr!r}"
    )
    skill_dirs = [p for p in custom.iterdir() if p.is_dir()] if custom.exists() else []
    assert skill_dirs, f"no skill directories found under {custom}"
    assert not (home / ".claude" / "skills").exists(), (
        f"{home}/.claude/skills should not be created when --skills-dest is declared"
    )


def test_declared_skills_dest_persists_across_a_later_run_with_no_flag(tmp_path):
    """The declared dest is persisted to `~/.claude/.tlor-install.conf`, so a
    later run with NO flag still installs skills to the same path."""
    home = tmp_path / "home"
    home.mkdir()
    custom = tmp_path / "custom"
    env = _env_with_home(home)

    proc1 = _run_install(env, [f"--skills-dest={custom}", "--force"])
    assert proc1.returncode == 0, (
        f"first run: expected exit 0, got {proc1.returncode}; stdout: "
        f"{proc1.stdout!r} stderr: {proc1.stderr!r}"
    )

    proc2 = _run_install(env, [])
    assert proc2.returncode == 0, (
        f"second run (no flag): expected exit 0, got {proc2.returncode}; "
        f"stdout: {proc2.stdout!r} stderr: {proc2.stderr!r}"
    )

    skill_dirs = [p for p in custom.iterdir() if p.is_dir()] if custom.exists() else []
    assert skill_dirs, f"no skill directories found under {custom} after second run"

    conf = home / ".claude" / ".tlor-install.conf"
    assert conf.exists(), f"{conf} was not created by the first run"
    assert f"skills_dest={custom}" in conf.read_text(encoding="utf-8").splitlines(), (
        f"{conf} does not contain the line 'skills_dest={custom}'"
    )


def test_no_flag_and_no_config_still_installs_skills_to_the_default_location(tmp_path):
    """Unchanged default: no flag, no config -> skills install to
    `$HOME/.claude/skills`."""
    home = tmp_path / "home"
    home.mkdir()
    env = _env_with_home(home)

    proc = _run_install(env, [])

    assert proc.returncode == 0, (
        f"expected exit 0, got {proc.returncode}; stdout: {proc.stdout!r} "
        f"stderr: {proc.stderr!r}"
    )
    default_skills = home / ".claude" / "skills"
    assert default_skills.is_dir(), f"{default_skills} was not created"
    skill_dirs = [p for p in default_skills.iterdir() if p.is_dir()]
    assert skill_dirs, f"no skill directories found under {default_skills}"


def test_no_flag_no_config_still_aborts_on_a_skills_symlink_outside_home(tmp_path):
    """Unchanged safety default: no flag, no config, `$HOME/.claude/skills`
    pre-created as a symlink to a directory outside the tmp HOME -> exit 1,
    and that outside directory's contents are unchanged."""
    home = tmp_path / "home"
    home.mkdir()
    outside = tmp_path / "outside_skills"
    outside.mkdir()
    marker = outside / "marker.txt"
    marker.write_text("original", encoding="utf-8")

    claude_dir = home / ".claude"
    claude_dir.mkdir()
    (claude_dir / "skills").symlink_to(outside, target_is_directory=True)

    env = _env_with_home(home)
    proc = _run_install(env, [])

    assert proc.returncode == 1, (
        f"expected exit 1, got {proc.returncode}; stdout: {proc.stdout!r} "
        f"stderr: {proc.stderr!r}"
    )
    assert list(outside.iterdir()) == [marker], (
        f"outside dir contents changed: {[p.name for p in outside.iterdir()]}"
    )
    assert marker.read_text(encoding="utf-8") == "original"


def test_declared_skills_dest_overrides_the_outside_symlink_abort(tmp_path):
    """Declaring `--skills-dest=<the outside dir>` overrides the abort that
    would otherwise fire for that same directory."""
    home = tmp_path / "home"
    home.mkdir()
    outside = tmp_path / "outside_skills2"
    outside.mkdir()

    claude_dir = home / ".claude"
    claude_dir.mkdir()
    (claude_dir / "skills").symlink_to(outside, target_is_directory=True)

    env = _env_with_home(home)
    proc = _run_install(env, [f"--skills-dest={outside}", "--force"])

    assert proc.returncode == 0, (
        f"expected exit 0, got {proc.returncode}; stdout: {proc.stdout!r} "
        f"stderr: {proc.stderr!r}"
    )
    skill_dirs = [p for p in outside.iterdir() if p.is_dir()]
    assert skill_dirs, f"no skill directories landed in {outside}"


def test_skills_dest_flag_rejects_relative_and_home_root_paths(tmp_path):
    """`--skills-dest=relative/path` and `--skills-dest=<HOME>` (the home
    root itself) are both rejected with exit 1 and a stderr message."""
    home = tmp_path / "home"
    home.mkdir()
    env = _env_with_home(home)

    proc_rel = _run_install(env, ["--skills-dest=relative/path"])
    assert proc_rel.returncode == 1, (
        f"relative path: expected exit 1, got {proc_rel.returncode}; "
        f"stdout: {proc_rel.stdout!r} stderr: {proc_rel.stderr!r}"
    )
    assert "unknown arg" not in proc_rel.stderr, (
        f"--skills-dest was not recognized as a flag at all: {proc_rel.stderr!r}"
    )
    assert "--skills-dest" in proc_rel.stderr, (
        "expected a --skills-dest-specific validation message on stderr for "
        f"a relative path, got: {proc_rel.stderr!r}"
    )

    proc_home = _run_install(env, [f"--skills-dest={home}"])
    assert proc_home.returncode == 1, (
        f"home-root path: expected exit 1, got {proc_home.returncode}; "
        f"stdout: {proc_home.stdout!r} stderr: {proc_home.stderr!r}"
    )
    assert "unknown arg" not in proc_home.stderr, (
        f"--skills-dest was not recognized as a flag at all: {proc_home.stderr!r}"
    )
    assert "--skills-dest" in proc_home.stderr, (
        "expected a --skills-dest-specific validation message on stderr for "
        f"the HOME-root path, got: {proc_home.stderr!r}"
    )


def test_declared_skills_dest_manifests_land_under_the_declared_path(tmp_path):
    """Manifests (`.tlor-manifest`, `.tlor-stdd-manifest`) follow the
    declared dest, not the default location."""
    home = tmp_path / "home"
    home.mkdir()
    custom = tmp_path / "custom7"
    env = _env_with_home(home)

    proc = _run_install(env, [f"--skills-dest={custom}", "--stdd-role=ALL", "--force"])

    assert proc.returncode == 0, (
        f"expected exit 0, got {proc.returncode}; stdout: {proc.stdout!r} "
        f"stderr: {proc.stderr!r}"
    )
    assert (custom / ".tlor-manifest").exists(), f"{custom}/.tlor-manifest missing"
    assert (custom / ".tlor-stdd-manifest").exists(), (
        f"{custom}/.tlor-stdd-manifest missing"
    )

    default_skills = home / ".claude" / "skills"
    assert not (default_skills / ".tlor-manifest").exists(), (
        f"{default_skills}/.tlor-manifest should not exist when --skills-dest is declared"
    )
    assert not (default_skills / ".tlor-stdd-manifest").exists(), (
        f"{default_skills}/.tlor-stdd-manifest should not exist when --skills-dest is declared"
    )


# --- agent_doc/ language subdir support (zh_tw/, en_us/) -------------------


def test_install_lands_agent_doc_language_subdir_files_and_manifest(tmp_path):
    """A fresh install copies `agent_doc/<lang>/*.md` (e.g. `zh_tw/`,
    `en_us/`) preserving the subdir path, and records each one in the
    agent_doc manifest as `<lang>/<file>.md`."""
    home = tmp_path / "home"
    home.mkdir()
    env = _env_with_home(home)

    proc = _run_install(env, ["--force"])
    assert proc.returncode == 0, (
        f"expected exit 0, got {proc.returncode}; stdout: {proc.stdout!r} "
        f"stderr: {proc.stderr!r}"
    )

    agent_doc_dir = home / ".claude" / "agent_doc"
    assert (agent_doc_dir / "zh_tw" / "patterns.md").is_file(), (
        f"{agent_doc_dir}/zh_tw/patterns.md was not installed"
    )
    assert (agent_doc_dir / "en_us" / "patterns.md").is_file(), (
        f"{agent_doc_dir}/en_us/patterns.md was not installed"
    )
    assert (agent_doc_dir / "bilbo-scribe.md").is_file(), (
        f"{agent_doc_dir}/bilbo-scribe.md was not installed"
    )

    manifest_lines = (agent_doc_dir / ".tlor-manifest").read_text(
        encoding="utf-8"
    ).splitlines()
    assert "zh_tw/patterns.md" in manifest_lines, (
        f"agent_doc manifest missing 'zh_tw/patterns.md': {manifest_lines}"
    )
    assert "en_us/patterns.md" in manifest_lines, (
        f"agent_doc manifest missing 'en_us/patterns.md': {manifest_lines}"
    )


def test_reinstall_of_agent_doc_language_subdir_files_is_idempotent(tmp_path):
    """Re-running install (no changes) still reports the subdir files
    installed/unchanged and exits 0 — no partial-install error."""
    home = tmp_path / "home"
    home.mkdir()
    env = _env_with_home(home)

    proc1 = _run_install(env, ["--force"])
    assert proc1.returncode == 0, f"first run failed: {proc1.stderr!r}"

    proc2 = _run_install(env, ["--force"])
    assert proc2.returncode == 0, (
        f"second run: expected exit 0, got {proc2.returncode}; stdout: "
        f"{proc2.stdout!r} stderr: {proc2.stderr!r}"
    )

    agent_doc_dir = home / ".claude" / "agent_doc"
    assert (agent_doc_dir / "zh_tw" / "patterns.md").is_file()
    assert (agent_doc_dir / "en_us" / "patterns.md").is_file()


def test_uninstall_removes_agent_doc_language_subdirs_but_customize_survives(
    tmp_path,
):
    """Uninstall removes the language-subdir files (and their now-empty
    subdir shells), while `agent_doc/customize/` (including its own
    one-level subdirs) — the user's own landing zone — survives untouched,
    with zero "skipping unsafe manifest entry" warnings for customize files.

    The pre-uninstall existence assertions below are load-bearing: without
    them this test would pass trivially against an install.sh that never
    implemented the subdir-install branch at all (nothing installed ->
    nothing to remove -> the post-uninstall "not exists" assertions are
    vacuously true).
    """
    home = tmp_path / "home"
    home.mkdir()
    env = _env_with_home(home)

    proc_install = _run_install(env, ["--force", "--with-optional"])
    assert proc_install.returncode == 0, (
        f"install failed: {proc_install.stdout!r} {proc_install.stderr!r}"
    )

    agent_doc_dir = home / ".claude" / "agent_doc"

    # Load-bearing: prove the subdir-install branch actually ran before
    # asserting anything about its removal.
    assert (agent_doc_dir / "zh_tw" / "patterns.md").is_file(), (
        "precondition failed: zh_tw/patterns.md was not installed — the "
        "subdir-install branch under test never ran"
    )
    assert (agent_doc_dir / "en_us" / "patterns.md").is_file(), (
        "precondition failed: en_us/patterns.md was not installed — the "
        "subdir-install branch under test never ran"
    )

    customize_dir = agent_doc_dir / "customize"
    customize_subdir = customize_dir / "zh_tw"
    customize_subdir.mkdir(parents=True, exist_ok=True)
    user_file = customize_dir / "user-added.md"
    user_file.write_text("user content\n", encoding="utf-8")
    user_subdir_file = customize_subdir / "user-added-sub.md"
    user_subdir_file.write_text("user subdir content\n", encoding="utf-8")

    proc_uninstall = _run_install(env, ["--uninstall"])
    assert proc_uninstall.returncode == 0, (
        f"uninstall failed: {proc_uninstall.stdout!r} {proc_uninstall.stderr!r}"
    )
    combined_output = proc_uninstall.stdout + proc_uninstall.stderr
    customize_warnings = [
        line
        for line in combined_output.splitlines()
        if "unsafe manifest entry" in line and "customize" in line
    ]
    assert not customize_warnings, (
        "uninstall must print zero 'skipping unsafe manifest entry' warnings "
        f"for customize files, got: {customize_warnings!r}"
    )

    assert not (agent_doc_dir / "zh_tw" / "patterns.md").exists(), (
        "zh_tw/patterns.md should have been removed by uninstall"
    )
    assert not (agent_doc_dir / "zh_tw").exists(), (
        "the now-empty zh_tw/ subdir shell should have been cleared by uninstall"
    )
    assert not (agent_doc_dir / "en_us").exists(), (
        "the now-empty en_us/ subdir shell should have been cleared by uninstall"
    )
    assert customize_dir.exists(), (
        "agent_doc/customize/ must survive uninstall — it's the user's own landing zone"
    )
    assert user_file.exists() and user_file.read_text(encoding="utf-8") == (
        "user content\n"
    ), "a pre-existing user file under agent_doc/customize/ must survive uninstall untouched"
    assert (
        customize_subdir.exists()
        and user_subdir_file.exists()
        and user_subdir_file.read_text(encoding="utf-8") == "user subdir content\n"
    ), (
        "a pre-existing user file under agent_doc/customize/zh_tw/ (a "
        "subdir under the user's own landing zone) must survive uninstall "
        "untouched"
    )
