# -*- coding: utf-8 -*-
"""Shared fixtures for the hook test suite.

Black-box only: hooks are invoked as subprocesses (python3 or bash), exactly
as Claude Code's PreToolUse/Stop hook wiring invokes them, with stdin JSON
and env overrides. No hook internals are imported directly.
"""
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
HOOKS_DIR = REPO_ROOT / "hooks"


class HookResult:
    """Result of one subprocess invocation of a hook script."""

    def __init__(self, returncode, stdout, stderr):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr

    @property
    def decision(self):
        """Parse stdout as JSON, or None if the hook printed nothing."""
        if not self.stdout.strip():
            return None
        return json.loads(self.stdout)


@pytest.fixture
def tmp_home(tmp_path):
    """A tmp dir usable as HOME; tests create .claude/... under it as needed."""
    home = tmp_path / "home"
    home.mkdir()
    return home


@pytest.fixture
def run_hook():
    """Run a hook script (.py via python3, .sh via bash) with the given
    stdin payload and env overrides. Returns a HookResult."""

    def _run(script_path, stdin_data, env_overrides=None, cwd=None, args=None):
        env = os.environ.copy()
        if env_overrides:
            env.update(env_overrides)
        script_path = str(script_path)
        if script_path.endswith(".py"):
            cmd = [sys.executable, script_path]
        else:
            # Absolute path: subprocess resolves cmd[0] against the env we
            # pass (not the ambient PATH), and tests may hand in a PATH with
            # bash deliberately absent from it.
            bash_path = shutil.which("bash") or "/bin/bash"
            cmd = [bash_path, script_path]
        if args:
            cmd.extend(args)
        if isinstance(stdin_data, dict):
            stdin_data = json.dumps(stdin_data)
        proc = subprocess.run(
            cmd,
            input=stdin_data,
            capture_output=True,
            text=True,
            env=env,
            cwd=str(cwd) if cwd else None,
        )
        return HookResult(proc.returncode, proc.stdout, proc.stderr)

    return _run


def have_jq():
    return shutil.which("jq") is not None
