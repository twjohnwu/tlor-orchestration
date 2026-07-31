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
      (covering all ten `mkdir -p` sites: install.sh:373,416,421,430,441,
      457,466,479,500,505).
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
