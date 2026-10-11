# -*- coding: utf-8 -*-
"""Black-box tests for hooks/test_queue_guard.py (PreToolUse Bash hook)."""
import subprocess

import pytest

from conftest import HOOKS_DIR

HOOK = HOOKS_DIR / "test_queue_guard.py"
ENV_ON = {"TLOR_TEST_QUEUE_GUARD": "1"}
QUEUE = "python3 /x/review_loop.py run-tests"


@pytest.fixture
def repo(tmp_path):
    root = tmp_path / "repo"
    (root / "sub" / "deep").mkdir(parents=True)
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    return root


def _local(repo, tests):
    (repo / "AGENTS.local.md").write_text(
        "# Local\n\n## Review loop\n\n- tests: %s\n" % tests, encoding="utf-8"
    )


def _payload(repo, command, background=False):
    return {
        "tool_name": "Bash",
        "tool_input": {"command": command, "run_in_background": background},
        "cwd": str(repo / "sub" / "deep"),
    }


def _reason(result):
    assert result.returncode == 0
    return result.decision["hookSpecificOutput"]["permissionDecisionReason"]


def test_env_off_allows(run_hook, repo):
    _local(repo, "never")
    result = run_hook(HOOK, _payload(repo, "pytest -q"))
    assert result.returncode == 0 and result.decision is None


def test_no_tests_key_allows(run_hook, repo):
    result = run_hook(HOOK, _payload(repo, "pytest -q"), env_overrides=ENV_ON)
    assert result.returncode == 0 and result.decision is None


def test_non_bash_tool_allows(run_hook, repo):
    _local(repo, "never")
    payload = _payload(repo, "pytest -q")
    payload["tool_name"] = "Write"
    result = run_hook(HOOK, payload, env_overrides=ENV_ON)
    assert result.decision is None


def test_never_denies_pytest(run_hook, repo):
    _local(repo, "never")
    result = run_hook(HOOK, _payload(repo, "pytest -q"), env_overrides=ENV_ON)
    assert "tests: never" in _reason(result)
    assert result.decision["hookSpecificOutput"]["permissionDecision"] == "deny"


def test_never_denies_queued_too(run_hook, repo):
    _local(repo, "never")
    cmd = QUEUE + " --cmd 'pytest -q'"
    result = run_hook(HOOK, _payload(repo, cmd), env_overrides=ENV_ON)
    assert "tests: never" in _reason(result)


def test_never_allows_ls(run_hook, repo):
    _local(repo, "never")
    result = run_hook(HOOK, _payload(repo, "ls -la"), env_overrides=ENV_ON)
    assert result.decision is None


def test_serial_denies_npm_test_naming_queue(run_hook, repo):
    _local(repo, "serial")
    result = run_hook(HOOK, _payload(repo, "npm test"), env_overrides=ENV_ON)
    reason = _reason(result)
    assert "review_loop.py run-tests --cmd" in reason
    assert "npm test" in reason


def test_serial_allows_queued(run_hook, repo):
    _local(repo, "serial")
    cmd = QUEUE + " --cmd 'pytest -q'"
    result = run_hook(HOOK, _payload(repo, cmd), env_overrides=ENV_ON)
    assert result.decision is None


def test_serial_denies_queued_background(run_hook, repo):
    _local(repo, "serial")
    cmd = QUEUE + " --cmd 'pytest -q'"
    result = run_hook(HOOK, _payload(repo, cmd, background=True), env_overrides=ENV_ON)
    assert "foreground only" in _reason(result)


def test_exact_test_command_match_denies(run_hook, repo):
    _local(repo, "serial")
    (repo / "AGENTS.md").write_text(
        "## Review loop\n\n- test-command: make check-all\n", encoding="utf-8"
    )
    result = run_hook(HOOK, _payload(repo, "cd x && make check-all"), env_overrides=ENV_ON)
    assert "run-tests" in _reason(result)


@pytest.mark.parametrize("cmd", [
    "grep jest file", "cat pytest.ini", "echo go test", "ls tests/pytest",
])
def test_non_test_words_allow(run_hook, repo, cmd):
    _local(repo, "never")
    result = run_hook(HOOK, _payload(repo, cmd), env_overrides=ENV_ON)
    assert result.decision is None


@pytest.mark.parametrize("cmd", [
    "cd a && go test ./...", "FOO=1 python3.12 -m pytest", "(cargo test)",
    "yarn run test", "make; npx jest", "echo hi | gradlew test",
])
def test_test_shapes_deny(run_hook, repo, cmd):
    _local(repo, "never")
    result = run_hook(HOOK, _payload(repo, cmd), env_overrides=ENV_ON)
    assert result.decision is not None, cmd


def test_unknown_tests_value_allows(run_hook, repo):
    _local(repo, "weird")
    result = run_hook(HOOK, _payload(repo, "pytest"), env_overrides=ENV_ON)
    assert result.decision is None


def test_malformed_stdin_allows(run_hook):
    result = run_hook(HOOK, "{not json", env_overrides=ENV_ON)
    assert result.returncode == 0 and result.decision is None


# segment classification (quote-aware, wrapper-stripping)


@pytest.mark.parametrize("cmd", [
    "/usr/local/bin/python3 -m pytest tests -q", "uv run pytest", "poetry run pytest",
    'bash -c "pytest"', "sh -c pytest", "make test", "yarn jest", "npm t",
    "pnpm vitest run", "tox", "timeout 600 pytest", "nice pytest",
    "env CI=1 pytest", "time pytest", "ctest", "dotnet test", "cd a && go test ./...",
    "pipenv run pytest", "bundle exec rspec", "pnpm exec jest", "nohup pytest",
    "nice -n 5 pytest", "zsh -c 'cd x; pytest -q'", "xcodebuild -scheme App test",
    "./gradlew test", "make check", "npm run test:unit", "pytest &", "echo $(pytest)",
    "for f in a b; do pytest $f; done", "if true; then pytest; fi",
    "while x; do pytest; done", "{ pytest; }", "! pytest",
    "if x; then a; else pytest; fi", "(" + QUEUE + ") &",
])
def test_never_denies_wrapped_and_aliased_tests(run_hook, repo, cmd):
    _local(repo, "never")
    result = run_hook(HOOK, _payload(repo, cmd), env_overrides=ENV_ON)
    assert "tests: never" in _reason(result), cmd


@pytest.mark.parametrize("cmd", [
    'git commit -m "wip; pytest flaky"', 'echo "please run make check later"',
    "echo pytest", "grep pytest x", "cat pytest.ini", "pip install pytest-cov",
    "git commit -F - <<'EOF'\nfix: flaky\n\npytest flaky on CI\nEOF",
    "git commit -m 'subject\n\npytest -q now passes'", "command -v pytest",
])
def test_never_allows_test_words_in_text(run_hook, repo, cmd):
    _local(repo, "never")
    (repo / "AGENTS.md").write_text(
        "## Review loop\n\n- test-command: pytest\n", encoding="utf-8"
    )
    result = run_hook(HOOK, _payload(repo, cmd), env_overrides=ENV_ON)
    assert result.returncode == 0 and result.decision is None, cmd


@pytest.mark.parametrize("cmd", [
    QUEUE + "; pytest", "pytest # review_loop.py run-tests",
    "echo review_loop.py run-tests && pytest", QUEUE + " --cmd 'ls' | pytest",
])
def test_serial_denies_queue_bypass(run_hook, repo, cmd):
    _local(repo, "serial")
    result = run_hook(HOOK, _payload(repo, cmd), env_overrides=ENV_ON)
    assert "run-tests --cmd" in _reason(result), cmd


@pytest.mark.parametrize("cmd", [
    QUEUE + " --cmd 'cd . && pytest; echo done'",
    "cd repo && /usr/local/bin/python3 /x/review_loop.py run-tests",
    "env CI=1 python3 /x/review_loop.py run-tests --cmd 'pytest -q'",
])
def test_serial_allows_queued_shapes(run_hook, repo, cmd):
    _local(repo, "serial")
    result = run_hook(HOOK, _payload(repo, cmd), env_overrides=ENV_ON)
    assert result.decision is None, cmd


@pytest.mark.parametrize("cmd", [
    "(" + QUEUE + ") &", "(cd x; " + QUEUE + ") &",
    "bash -c '" + QUEUE + "' &", "sh -c \"" + QUEUE + "\" &",
])
def test_serial_denies_queued_group_background(run_hook, repo, cmd):
    _local(repo, "serial")
    result = run_hook(HOOK, _payload(repo, cmd), env_overrides=ENV_ON)
    assert "foreground only" in _reason(result), cmd


@pytest.mark.parametrize("cmd", [
    "(" + QUEUE + ") && echo done", "bash -c '" + QUEUE + "'",
])
def test_serial_allows_queued_group_foreground(run_hook, repo, cmd):
    _local(repo, "serial")
    result = run_hook(HOOK, _payload(repo, cmd), env_overrides=ENV_ON)
    assert result.decision is None, cmd


def test_serial_denies_queued_shell_background(run_hook, repo):
    _local(repo, "serial")
    result = run_hook(HOOK, _payload(repo, QUEUE + " &"), env_overrides=ENV_ON)
    assert "foreground only" in _reason(result)


def test_serial_deny_suggests_wrapping_original_command(run_hook, repo):
    _local(repo, "serial")
    result = run_hook(HOOK, _payload(repo, "cd a && go test ./..."), env_overrides=ENV_ON)
    assert "review_loop.py run-tests --cmd 'cd a && go test ./...'" in _reason(result)


def test_test_command_segment_match_is_whitespace_normalized(run_hook, repo):
    _local(repo, "never")
    (repo / "AGENTS.md").write_text(
        "## Review loop\n\n- test-command: ./scripts/run-checks.sh  --fast\n",
        encoding="utf-8",
    )
    hit = run_hook(HOOK, _payload(repo, "ls; ./scripts/run-checks.sh --fast"), env_overrides=ENV_ON)
    assert hit.decision is not None
    miss = run_hook(HOOK, _payload(repo, "cat ./scripts/run-checks.sh"), env_overrides=ENV_ON)
    assert miss.decision is None


def test_hook_parses_as_python_37():
    import ast
    source = HOOK.read_text(encoding="utf-8")
    try:
        ast.parse(source, feature_version=(3, 7))
    except TypeError:
        # Python 3.7 predates feature_version; its own parser is the target.
        ast.parse(source)


# review-fix round 3: package-manager option values, real queue path


@pytest.mark.parametrize("cmd", [
    "pnpm --filter web test", "npm --prefix web test", "yarn --cwd web test",
    "pnpm -C web test", "npm -w web test", "pnpm -F web test",
    "yarn workspace web test", "npm --workspace web run test:unit",
    "pnpm --dir web run test", "bun --cwd web test", "pnpm -w test",
])
def test_never_denies_package_manager_option_values(run_hook, repo, cmd):
    _local(repo, "never")
    result = run_hook(HOOK, _payload(repo, cmd), env_overrides=ENV_ON)
    assert "tests: never" in _reason(result), cmd


@pytest.mark.parametrize("cmd", [
    "npm install test-utils", "pnpm add -D vitest", "yarn workspace web add test-utils",
    "npm --prefix web install", "pnpm --filter web build",
])
def test_never_allows_package_manager_non_tests(run_hook, repo, cmd):
    _local(repo, "never")
    result = run_hook(HOOK, _payload(repo, cmd), env_overrides=ENV_ON)
    assert result.returncode == 0 and result.decision is None, cmd


def test_serial_deny_names_installed_queue_script(run_hook, repo, tmp_home):
    import os
    _local(repo, "serial")
    script = tmp_home / ".claude" / "skills" / "stdd-review-loop" / "references" / "review_loop.py"
    script.parent.mkdir(parents=True)
    script.write_text("", encoding="utf-8")
    result = run_hook(
        HOOK, _payload(repo, "pytest -q"),
        env_overrides=dict(ENV_ON, HOME=str(tmp_home)),
    )
    reason = _reason(result)
    assert str(script) + " run-tests --cmd 'pytest -q'" in reason
    assert "<path>" not in reason and os.path.isfile(str(script))


def test_serial_deny_falls_back_to_repo_layout_script(run_hook, repo, tmp_home):
    import os
    _local(repo, "serial")
    result = run_hook(
        HOOK, _payload(repo, "pytest -q"),
        env_overrides=dict(ENV_ON, HOME=str(tmp_home)),
    )
    reason = _reason(result)
    path = reason.split("python3 ", 1)[1].split(" run-tests", 1)[0]
    assert path.endswith("review_loop.py") and os.path.isfile(path), reason
