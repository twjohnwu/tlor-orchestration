# -*- coding: utf-8 -*-
"""Tests for the GitHub/GitLab review-loop helper."""
import ast
import json
import os
import shlex
import subprocess
import sys
import time
from pathlib import Path

import pytest

from conftest import REPO_ROOT

REFERENCES = REPO_ROOT / "stdd-skills" / "stdd-review-loop" / "references"
sys.path.insert(0, str(REFERENCES))
sys.dont_write_bytecode = True
import review_loop

SCRIPT = REFERENCES / "review_loop.py"
PY = sys.executable


def run_cli(args, env=None, stdin=""):
    process_env = os.environ.copy()
    process_env["REVIEW_LOOP_SLEEP_SCALE"] = "0"
    if env:
        process_env.update(env)
    return subprocess.run(
        [PY, str(SCRIPT)] + args,
        input=stdin,
        capture_output=True,
        universal_newlines=True,
        env=process_env,
    )


def payload(proc, expected_code=0):
    assert proc.returncode == expected_code, proc.stdout + proc.stderr
    assert len(proc.stdout.splitlines()) == 1
    return json.loads(proc.stdout)


def write_cli(tmp_path, name, source):
    path = tmp_path / name
    path.write_text("#!/usr/bin/env python3\n" + source, encoding="utf-8")
    path.chmod(0o755)
    return path


def cli_path(tmp_path):
    return str(tmp_path) + os.pathsep + os.environ.get("PATH", "")


# parse_review


def test_parse_heading_sections_and_path_line():
    result = review_loop.parse_review(
        "### Critical\n- `src/auth/token.py:123` accepts an expired token\n"
        "#### Low (2)\n1. docs/readme.md:8 could be clearer\n"
    )
    assert result["verdict"] == "changes"
    assert result["blocking_count"] == 1
    assert result["findings"][0] == {
        "n": 1,
        "severity": "critical",
        "blocking": True,
        "path": "src/auth/token.py",
        "line": 123,
        "text": "`src/auth/token.py:123` accepts an expired token",
    }
    assert result["findings"][1]["severity"] == "low"
    assert result["findings"][1]["blocking"] is False


def test_parse_inline_tag_styles():
    result = review_loop.parse_review(
        "- [High] first\n"
        "* **Medium**: second\n"
        "1. Severity: Low third\n"
        "- (nit) fourth\n"
        "- Nit: fifth\n"
    )
    assert [item["severity"] for item in result["findings"]] == [
        "high", "medium", "low", "nit", "nit"
    ]
    assert result["blocking_count"] == 2


def test_parse_unknown_severity_is_fail_safe_blocking():
    result = review_loop.parse_review("- [Urgent] investigate race\n")
    assert result["findings"][0]["severity"] == "urgent"
    assert result["findings"][0]["blocking"] is True
    assert result["verdict"] == "changes"


def test_parse_lgtm_only_has_no_findings():
    result = review_loop.parse_review("LGTM\n")
    assert result == {"verdict": "lgtm", "findings": [], "blocking_count": 0}


def test_parse_nit_only_is_nonblocking():
    result = review_loop.parse_review("### Nit\n- rename this helper\n\nApproved\n")
    assert result["verdict"] == "lgtm"
    assert result["blocking_count"] == 0
    assert len(result["findings"]) == 1


# replace_section


def test_replace_section_replaces_once_and_preserves_following_heading():
    original = "Intro\n\n## AI Review Fixes\nold\n\n## Notes\nkeep\n"
    section = "## AI Review Fixes\nnew\n"
    updated, replaced = review_loop.replace_section(original, section)
    assert replaced is True
    assert updated.count("## AI Review Fixes") == 1
    assert "old" not in updated
    assert updated.endswith("## Notes\nkeep\n")


def test_replace_section_appends_when_absent():
    updated, replaced = review_loop.replace_section("Intro", "## AI Review Fixes\nnew\n")
    assert replaced is False
    assert updated == "Intro\n\n## AI Review Fixes\nnew\n"


# record


def test_record_creates_file_and_writes_job(tmp_path):
    agents = tmp_path / "AGENTS.md"
    result = payload(
        run_cli(["record", "--agents", str(agents), "--minutes", "4.2", "--job", "AI Review"])
    )
    assert result["minutes_written"] is True
    assert result["job_written"] is True
    assert result["ci_wait_minutes"] == 5
    assert result["review_job_name"] == "AI Review"
    assert agents.read_text(encoding="utf-8") == (
        "## Review loop\n- ci-wait-minutes: 5\n- review-job-name: AI Review\n"
    )


def test_record_twenty_percent_rule_and_preserves_other_content(tmp_path):
    agents = tmp_path / "AGENTS.md"
    original = "# Instructions\n\nKeep this byte-for-byte.\n"
    agents.write_text(original, encoding="utf-8")
    first = payload(run_cli(["record", "--agents", str(agents), "--minutes", "10"]))
    assert first["ci_wait_minutes"] == 10
    after_ten = agents.read_text(encoding="utf-8")
    eleven = payload(run_cli(["record", "--agents", str(agents), "--minutes", "11"]))
    assert eleven["minutes_written"] is False
    assert eleven["ci_wait_minutes"] == 10
    assert agents.read_text(encoding="utf-8") == after_ten
    thirteen = payload(run_cli(["record", "--agents", str(agents), "--minutes", "13"]))
    assert thirteen["minutes_written"] is True
    assert thirteen["ci_wait_minutes"] == 13
    assert agents.read_text(encoding="utf-8").startswith(original)


def test_record_show_reads_without_writing(tmp_path):
    agents = tmp_path / "AGENTS.md"
    content = "## Review loop\n- ci-wait-minutes: 7\n- review-job-name: bot-review\n"
    agents.write_text(content, encoding="utf-8")
    result = payload(run_cli(["record", "--agents", str(agents), "--show"]))
    assert result["minutes_written"] is False
    assert result["job_written"] is False
    assert result["ci_wait_minutes"] == 7
    assert result["review_job_name"] == "bot-review"
    assert agents.read_text(encoding="utf-8") == content


def test_record_preserves_unrelated_crlf_bytes(tmp_path):
    agents = tmp_path / "AGENTS.md"
    agents.write_bytes(
        b"# Rules\r\n\r\nkeep\r\n\r\n## Review loop\r\n"
        b"- ci-wait-minutes: 10\r\n- custom: untouched\r\n"
    )
    result = payload(run_cli(["record", "--agents", str(agents), "--minutes", "13"]))
    assert result["minutes_written"] is True
    assert agents.read_bytes() == (
        b"# Rules\r\n\r\nkeep\r\n\r\n## Review loop\r\n"
        b"- ci-wait-minutes: 13\n- custom: untouched\r\n"
    )


def test_record_round_trips_repo_commands_and_max_rounds(tmp_path):
    agents = tmp_path / "AGENTS.md"
    written = payload(
        run_cli(
            [
                "record", "--agents", str(agents), "--max-rounds", "6",
                "--test-command", "python -m pytest -q",
                "--lint-command", "python -m ruff check .",
            ]
        )
    )
    assert written["max_rounds"] == 6
    assert written["test_command"] == "python -m pytest -q"
    assert written["lint_command"] == "python -m ruff check ."
    assert agents.read_text(encoding="utf-8") == (
        "## Review loop\n"
        "- max-rounds: 6\n"
        "- test-command: python -m pytest -q\n"
        "- lint-command: python -m ruff check .\n"
    )
    shown = payload(run_cli(["record", "--agents", str(agents), "--show"]))
    assert shown["max_rounds"] == 6
    assert shown["test_command"] == "python -m pytest -q"
    assert shown["lint_command"] == "python -m ruff check ."


def test_record_local_writes_only_tests_setting(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=str(repo), check=True)
    (repo / ".gitignore").write_text("AGENTS.local.md\n", encoding="utf-8")
    agents = repo / "AGENTS.md"
    agents.write_text("## Review loop\n- max-rounds: 4\n", encoding="utf-8")
    result = payload(
        run_cli(["record", "--agents", str(agents), "--local", "--tests", "serial"])
    )
    local = repo / "AGENTS.local.md"
    assert result["path"] == str(local)
    assert result["tests"] == "serial"
    assert "warning" not in result
    assert local.read_text(encoding="utf-8") == "## Review loop\n- tests: serial\n"


def test_record_show_merges_local_and_defaults(tmp_path):
    agents = tmp_path / "AGENTS.md"
    agents.write_text(
        "## Review loop\n- review-job-name: review\n- test-command: python tests.py\n",
        encoding="utf-8",
    )
    (tmp_path / "AGENTS.local.md").write_text(
        "## Review loop\n- tests: serial\n", encoding="utf-8"
    )
    result = payload(run_cli(["record", "--agents", str(agents), "--show"]))
    assert result["review_job_name"] == "review"
    assert result["max_rounds"] == 10
    assert result["test_command"] == "python tests.py"
    assert result["lint_command"] is None
    assert result["tests"] == "serial"

    (tmp_path / "AGENTS.local.md").unlink()
    result = payload(run_cli(["record", "--agents", str(agents), "--show"]))
    assert result["tests"] == "never"


def test_record_local_warns_when_not_gitignored(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=str(repo), check=True)
    agents = repo / "AGENTS.md"
    result = payload(
        run_cli(["record", "--agents", str(agents), "--local", "--tests", "never"])
    )
    assert result["warning"] == "AGENTS.local.md is not gitignored; add it to .gitignore"
    assert (repo / "AGENTS.local.md").exists()


@pytest.mark.parametrize(
    "contents,args",
    [
        ("", ["--max-rounds", "0"]),
        ("## Review loop\n- max-rounds: nope\n", ["--show"]),
        ("## Review loop\n- tests: sometimes\n", ["--show"]),
    ],
)
def test_record_rejects_invalid_settings(tmp_path, contents, args):
    agents = tmp_path / "AGENTS.md"
    target = tmp_path / ("AGENTS.local.md" if "tests:" in contents else "AGENTS.md")
    target.write_text(contents, encoding="utf-8")
    proc = run_cli(["record", "--agents", str(agents)] + args)
    result = payload(proc, expected_code=1)
    assert result["error"]


# fake CLI integration


def test_preflight_not_installed(tmp_path):
    result = payload(
        run_cli(["preflight", "--platform", "github"], {"PATH": str(tmp_path)})
    )
    assert result == {
        "platform": "github",
        "branch": None,
        "cli": "gh",
        "installed": False,
        "logged_in": False,
        "hint": "brew install gh",
    }


def test_preflight_not_logged_in_discards_auth_output(tmp_path):
    write_cli(
        tmp_path,
        "gh",
        "import sys\nprint('sensitive auth output')\nsys.exit(1)\n",
    )
    proc = run_cli(["preflight", "--platform", "github"], {"PATH": cli_path(tmp_path)})
    result = payload(proc)
    assert result["installed"] is True
    assert result["logged_in"] is False
    assert result["hint"] == "! gh auth login"
    assert "sensitive" not in proc.stdout


def test_preflight_ready_with_glab(tmp_path):
    write_cli(tmp_path, "glab", "import sys\nsys.exit(0)\n")
    result = payload(
        run_cli(["preflight", "--platform", "gitlab"], {"PATH": cli_path(tmp_path)})
    )
    assert result["cli"] == "glab"
    assert result["installed"] is True
    assert result["logged_in"] is True
    assert result["hint"] == ""


def test_wait_success_with_failed_non_review_job(tmp_path):
    write_cli(
        tmp_path,
        "gh",
        "import json, sys\n"
        "if sys.argv[1:3] == ['pr', 'checks']:\n"
        " print(json.dumps([{'name':'AI Code Review','state':'SUCCESS','bucket':'pass'},"
        "{'name':'lint','state':'FAILURE','bucket':'fail'}]))\n"
        " sys.exit(1)\n"
        "sys.exit(2)\n",
    )
    result = payload(
        run_cli(["wait", "--platform", "github", "--minutes", "2"], {"PATH": cli_path(tmp_path)})
    )
    assert result["status"] == "failed"
    assert result["review_job"] == "AI Code Review"
    assert result["failed_jobs"] == ["lint"]
    assert result["waited_minutes"] == 2.0
    assert result["extensions"] == 0


def test_wait_running_then_success_after_one_extension(tmp_path):
    counter = tmp_path / "count"
    write_cli(
        tmp_path,
        "gh",
        "import json, os, pathlib, sys\n"
        "p=pathlib.Path(os.environ['COUNTER'])\n"
        "n=int(p.read_text())+1 if p.exists() else 1\n"
        "p.write_text(str(n))\n"
        "state=('IN_PROGRESS','pending') if n == 1 else ('SUCCESS','pass')\n"
        "print(json.dumps([{'name':'review','state':state[0],'bucket':state[1]}]))\n",
    )
    result = payload(
        run_cli(
            ["wait", "--platform", "github", "--minutes", "3"],
            {"PATH": cli_path(tmp_path), "COUNTER": str(counter)},
        )
    )
    assert result["status"] == "success"
    assert result["extensions"] == 1
    assert result["waited_minutes"] == 6.0


def test_wait_extensions_exhausted_is_running(tmp_path):
    write_cli(
        tmp_path,
        "gh",
        "import json\nprint(json.dumps([{'name':'review','state':'QUEUED','bucket':'pending'}]))\n",
    )
    result = payload(
        run_cli(
            ["wait", "--platform", "github", "--minutes", "1", "--max-extensions", "2"],
            {"PATH": cli_path(tmp_path)},
        )
    )
    assert result["status"] == "running"
    assert result["extensions"] == 2
    assert result["waited_minutes"] == 3.0


def test_gitlab_wait_success(tmp_path):
    write_cli(
        tmp_path,
        "glab",
        "import json, sys\n"
        "a=sys.argv[1:]\n"
        "if a[:2] == ['mr','view']:\n print(json.dumps({'iid':9,'head_pipeline':{'id':44}}))\n"
        "elif a and a[0] == 'api':\n print(json.dumps([{'name':'ai-review','status':'success'}]))\n"
        "else:\n sys.exit(2)\n",
    )
    result = payload(
        run_cli(["wait", "--platform", "gitlab", "--minutes", "0"], {"PATH": cli_path(tmp_path)})
    )
    assert result["status"] == "success"
    assert result["review_job_status"] == "success"


def rest(login, body, created, kind="User", key="created_at"):
    """A GitHub REST comment/review as `gh api` returns it."""
    return {"user": {"login": login, "type": kind}, key: created, "body": body}


def gh_rest_cli(tmp_path, issue=(), reviews=(), inline=(), log=None):
    """Stub gh serving `pr view` plus the three paginated REST endpoints for PR 7."""
    source = (
        "import json, os, pathlib, sys\n"
        "a=sys.argv[1:]\n"
        "if os.environ.get('LOG'):\n"
        " p=pathlib.Path(os.environ['LOG'])\n"
        " p.write_text((p.read_text() if p.exists() else '')+json.dumps(a)+'\\n')\n"
        "base='repos/{owner}/{repo}/'\n"
        "if a[:2] == ['api','user']:\n print('me')\n"
        "elif a[:2] == ['pr','view']:\n print(json.dumps({'number':7}))\n"
        "elif a == ['api','--paginate',base+'issues/7/comments']:\n print(json.dumps(" + repr(list(issue)) + "))\n"
        "elif a == ['api','--paginate',base+'pulls/7/reviews']:\n print(json.dumps(" + repr(list(reviews)) + "))\n"
        "elif a == ['api','--paginate',base+'pulls/7/comments']:\n print(json.dumps(" + repr(list(inline)) + "))\n"
        "else:\n sys.exit(2)\n"
    )
    write_cli(tmp_path, "gh", source)


def test_fetch_review_found_after_two_empty_attempts(tmp_path):
    counter = tmp_path / "fetch-count"
    write_cli(
        tmp_path,
        "gh",
        "import json, os, pathlib, sys\n"
        "if sys.argv[1:3] == ['api', 'user']:\n print('me')\n sys.exit(0)\n"
        "if sys.argv[1:3] == ['pr', 'view']:\n print(json.dumps({'number':7}))\n sys.exit(0)\n"
        "if 'reviews' in sys.argv[-1] or 'pulls/7/comments' in sys.argv[-1]:\n print('[]')\n sys.exit(0)\n"
        "p=pathlib.Path(os.environ['COUNTER'])\n"
        "n=int(p.read_text())+1 if p.exists() else 1\n"
        "p.write_text(str(n))\n"
        "comments=[] if n < 3 else [{'user':{'login':'bot[bot]','type':'Bot'},'body':'Code review: LGTM',"
        "'created_at':'2026-01-01T00:00:01Z'}]\n"
        "print(json.dumps(comments))\n",
    )
    result = payload(
        run_cli(
            ["fetch-review", "--platform", "github", "--since", "2026-01-01T00:00:00Z", "--retries", "4"],
            {"PATH": cli_path(tmp_path), "COUNTER": str(counter)},
        )
    )
    assert result["found"] is True
    assert result["author"] == "bot[bot]"
    assert result["attempts"] == 3


def test_fetch_review_not_found_after_retries(tmp_path):
    gh_rest_cli(tmp_path)
    result = payload(
        run_cli(
            ["fetch-review", "--platform", "github", "--since", "2026-01-01T00:00:00Z", "--retries", "2"],
            {"PATH": cli_path(tmp_path)},
        )
    )
    assert result == {"found": False, "body": "", "author": "", "created_at": "", "attempts": 3}


def test_fetch_review_since_is_strict_and_chooses_newest(tmp_path):
    gh_rest_cli(
        tmp_path,
        issue=[
            rest("bot[bot]", "Review at boundary", "2026-01-01T00:00:00Z", "Bot"),
            rest("bot[bot]", "Review newer", "2026-01-01T00:00:02+00:00", "Bot"),
            rest("bot[bot]", "Review newest", "2026-01-01T00:00:03Z", "Bot"),
        ],
    )
    result = payload(
        run_cli(
            ["fetch-review", "--platform", "github", "--since", "2026-01-01T00:00:00Z", "--retries", "0"],
            {"PATH": cli_path(tmp_path)},
        )
    )
    assert result["body"] == "Review newest"
    assert result["created_at"] == "2026-01-01T00:00:03Z"


def test_fetch_review_author_is_exact_and_does_not_require_bot(tmp_path):
    gh_rest_cli(
        tmp_path,
        issue=[
            rest("Reviewer", "Review exact", "2026-01-01T00:00:01Z"),
            rest("reviewer", "Review wrong case", "2026-01-01T00:00:03Z"),
            rest("someone", "Review newest human", "2026-01-01T00:00:04Z"),
        ],
    )
    result = payload(
        run_cli(
            [
                "fetch-review", "--platform", "github", "--since", "2026-01-01T00:00:00Z",
                "--author", "Reviewer", "--retries", "0",
            ],
            {"PATH": cli_path(tmp_path)},
        )
    )
    assert result["author"] == "Reviewer"
    assert result["body"] == "Review exact"


def test_fetch_review_without_author_prefers_older_bot_to_newer_human(tmp_path):
    gh_rest_cli(
        tmp_path,
        issue=[
            rest("review-service[bot]", "Review from bot", "2026-01-01T00:00:01Z", "Bot"),
            rest("human", "Review from human", "2026-01-01T00:00:03Z"),
        ],
    )
    result = payload(
        run_cli(
            ["fetch-review", "--platform", "github", "--since", "2026-01-01T00:00:00Z", "--retries", "0"],
            {"PATH": cli_path(tmp_path)},
        )
    )
    assert result["author"] == "review-service[bot]"
    assert result["body"] == "Review from bot"


def test_fetch_review_finds_rest_bot_review_unlocked(tmp_path):
    gh_rest_cli(
        tmp_path,
        reviews=[rest("x[bot]", "Review: LGTM", "2026-01-01T00:00:01Z", "Bot", key="submitted_at")],
    )
    result = payload(
        run_cli(
            ["fetch-review", "--platform", "github", "--since", "2026-01-01T00:00:00Z", "--retries", "0"],
            {"PATH": cli_path(tmp_path)},
        )
    )
    assert result["found"] is True
    assert result["author"] == "x[bot]"
    assert result["created_at"] == "2026-01-01T00:00:01Z"


def test_fetch_review_type_bot_without_suffix_is_bot(tmp_path):
    gh_rest_cli(tmp_path, issue=[rest("svc", "Review ok", "2026-01-01T00:00:01Z", "Bot")])
    result = payload(
        run_cli(
            ["fetch-review", "--platform", "github", "--since", "2026-01-01T00:00:00Z", "--retries", "0"],
            {"PATH": cli_path(tmp_path)},
        )
    )
    assert result["author"] == "svc"


def test_fetch_review_without_author_reports_human_candidates(tmp_path):
    gh_rest_cli(
        tmp_path,
        issue=[
            rest("sam", "Review first", "2026-01-01T00:00:01Z"),
            rest("alex", "Review newest", "2026-01-01T00:00:04Z"),
            rest("sam", "Review again", "2026-01-01T00:00:03Z"),
        ],
    )
    result = payload(
        run_cli(
            ["fetch-review", "--platform", "github", "--since", "2026-01-01T00:00:00Z", "--retries", "0"],
            {"PATH": cli_path(tmp_path)},
        ),
        expected_code=3,
    )
    assert result == {"found": False, "candidate_authors": ["alex", "sam"], "attempts": 1}


def test_fetch_review_human_user_type_is_exit_3(tmp_path):
    gh_rest_cli(tmp_path, issue=[rest("x", "Review by a human", "2026-01-01T00:00:01Z", "User")])
    result = payload(
        run_cli(
            ["fetch-review", "--platform", "github", "--since", "2026-01-01T00:00:00Z", "--retries", "0"],
            {"PATH": cli_path(tmp_path)},
        ),
        expected_code=3,
    )
    assert result == {"found": False, "candidate_authors": ["x"], "attempts": 1}


def test_candidate_authors_are_normalized_without_bot_suffix():
    comments = [
        {"user": {"login": "x[bot]", "type": "Bot"}, "body": "review", "created_at": "2026-01-01T00:00:02Z"},
        {"user": {"login": "x"}, "body": "review", "created_at": "2026-01-01T00:00:03Z"},
    ]
    assert review_loop._candidate_authors(
        comments, review_loop.parse_utc_timestamp("2026-01-01T00:00:00Z"), review_loop.DEFAULT_COMMENT_PATTERN, ()
    ) == ["x"]


def test_fetch_review_author_matches_with_or_without_bot_suffix(tmp_path):
    gh_rest_cli(tmp_path, issue=[rest("x[bot]", "Review by bot", "2026-01-01T00:00:01Z", "Bot")])
    for requested in ("x", "x[bot]"):
        result = payload(
            run_cli(
                [
                    "fetch-review", "--platform", "github", "--since", "2026-01-01T00:00:00Z",
                    "--author", requested, "--retries", "0",
                ],
                {"PATH": cli_path(tmp_path)},
            )
        )
        assert result["found"] is True, requested
        assert result["author"] == "x[bot]"
    gh_rest_cli(tmp_path, issue=[rest("x", "Review by plain login", "2026-01-01T00:00:01Z")])
    result = payload(
        run_cli(
            [
                "fetch-review", "--platform", "github", "--since", "2026-01-01T00:00:00Z",
                "--author", "x[bot]", "--retries", "0",
            ],
            {"PATH": cli_path(tmp_path)},
        )
    )
    assert result["author"] == "x"


def test_github_rest_calls_are_all_paginated(tmp_path):
    log = tmp_path / "calls"
    gh_rest_cli(tmp_path)
    payload(
        run_cli(
            ["fetch-comments", "--platform", "github", "--pr", "7", "--since", "2026-01-01T00:00:00Z"],
            {"PATH": cli_path(tmp_path), "LOG": str(log)},
        )
    )
    calls = [json.loads(line) for line in log.read_text(encoding="utf-8").splitlines()]
    rest_calls = [call for call in calls if call[0] == "api" and call[1] != "user"]
    assert sorted(call[-1] for call in rest_calls) == [
        "repos/{owner}/{repo}/issues/7/comments",
        "repos/{owner}/{repo}/pulls/7/comments",
        "repos/{owner}/{repo}/pulls/7/reviews",
    ]
    assert all("--paginate" in call for call in rest_calls)


def test_github_paginated_pages_are_concatenated():
    pages = "[1,2]\n[3]"
    proc = type("Proc", (), {"stdout": pages})()
    original = review_loop._run
    review_loop._run = lambda args, **kwargs: proc
    try:
        assert review_loop._paginated_json(["gh", "api", "--paginate", "x"]) == [1, 2, 3]
    finally:
        review_loop._run = original


def test_fetch_comments_github_collects_issue_review_and_inline_comments(tmp_path):
    gh_rest_cli(
        tmp_path,
        issue=[
            rest("issue-human", "issue", "2026-01-01T00:00:02Z"),
            rest("me", "self", "2026-01-01T00:00:06Z"),
            rest("old-human", "old", "2025-12-31T23:59:59Z"),
        ],
        reviews=[rest("review-human", "review", "2026-01-01T00:00:03Z", key="submitted_at")],
        inline=[
            dict(
                rest("inline-human", "inline", "2026-01-01T00:00:04Z"),
                path="src/a.py", line=None, original_line=9,
            ),
            rest("review-bot[bot]", "bot", "2026-01-01T00:00:05Z", "Bot"),
        ],
    )
    result = payload(
        run_cli(
            [
                "fetch-comments", "--platform", "github", "--pr", "7",
                "--since", "2026-01-01T00:00:00Z", "--exclude-author", "review-bot[bot]",
            ],
            {"PATH": cli_path(tmp_path)},
        )
    )
    assert result["comments"] == [
        {"author": "issue-human", "created_at": "2026-01-01T00:00:02Z", "body": "issue"},
        {"author": "review-human", "created_at": "2026-01-01T00:00:03Z", "body": "review"},
        {
            "author": "inline-human", "created_at": "2026-01-01T00:00:04Z",
            "body": "inline", "path": "src/a.py", "line": 9,
        },
    ]
    assert set(result) == {"comments", "checked_at"}


def test_fetch_comments_exclude_author_matches_bot_suffix_on_inline(tmp_path):
    gh_rest_cli(
        tmp_path,
        inline=[
            rest("x[bot]", "bot inline", "2026-01-01T00:00:05Z", "Bot"),
            rest("keeper", "human inline", "2026-01-01T00:00:06Z"),
        ],
    )
    result = payload(
        run_cli(
            [
                "fetch-comments", "--platform", "github", "--pr", "7",
                "--since", "2026-01-01T00:00:00Z", "--exclude-author", "x",
            ],
            {"PATH": cli_path(tmp_path)},
        )
    )
    assert [item["author"] for item in result["comments"]] == ["keeper"]


def test_fetch_comments_skips_empty_and_whitespace_bodies(tmp_path):
    gh_rest_cli(
        tmp_path,
        issue=[rest("human", "real", "2026-01-01T00:00:02Z")],
        reviews=[
            rest("approver", "", "2026-01-01T00:00:03Z", key="submitted_at"),
            rest("container", " \n\t", "2026-01-01T00:00:04Z", key="submitted_at"),
        ],
    )
    result = payload(
        run_cli(
            ["fetch-comments", "--platform", "github", "--pr", "7", "--since", "2026-01-01T00:00:00Z"],
            {"PATH": cli_path(tmp_path)},
        )
    )
    assert [item["author"] for item in result["comments"]] == ["human"]


def test_fetch_comments_returns_checked_at_taken_before_fetching(tmp_path):
    gh_rest_cli(tmp_path)
    before = review_loop.parse_utc_timestamp(review_loop._utc_iso(review_loop.datetime.datetime.now(review_loop.datetime.timezone.utc)))
    result = payload(
        run_cli(
            ["fetch-comments", "--platform", "github", "--pr", "7", "--since", "2026-01-01T00:00:00Z"],
            {"PATH": cli_path(tmp_path)},
        )
    )
    assert result["comments"] == []
    assert result["checked_at"].endswith("Z")
    assert review_loop.parse_utc_timestamp(result["checked_at"]) >= before


def test_fetch_comments_gitlab_collects_notes_with_positions(tmp_path):
    write_cli(
        tmp_path,
        "glab",
        "import json, sys\n"
        "a=sys.argv[1:]\n"
        "if a[:2] == ['api','user']:\n print(json.dumps({'username':'me'}))\n"
        "elif a[:2] == ['mr','view']:\n print(json.dumps({'iid':9,'sha':'abc'}))\n"
        "elif a and a[0] == 'api':\n"
        " print(json.dumps(["
        "{'author':{'username':'position-human'},'body':'positioned','created_at':'2026-01-01T00:00:04Z','position':{'new_path':'lib/a.rb','new_line':12}},"
        "{'author':{'username':'plain-human'},'body':'plain','created_at':'2026-01-01T00:00:02Z'},"
        "{'author':{'username':'me'},'body':'self','created_at':'2026-01-01T00:00:06Z'},"
        "{'author':{'username':'review-bot','bot':True},'body':'bot','created_at':'2026-01-01T00:00:05Z'},"
        "{'author':{'username':'system'},'body':'system','created_at':'2026-01-01T00:00:03Z','system':True},"
        "{'author':{'username':'old-human'},'body':'old','created_at':'2025-12-31T23:59:59Z'}]))\n"
        "else:\n sys.exit(2)\n",
    )
    result = payload(
        run_cli(
            [
                "fetch-comments", "--platform", "gitlab", "--pr", "9",
                "--since", "2026-01-01T00:00:00Z", "--exclude-author", "review-bot",
            ],
            {"PATH": cli_path(tmp_path)},
        )
    )
    assert result["comments"] == [
        {"author": "plain-human", "created_at": "2026-01-01T00:00:02Z", "body": "plain"},
        {
            "author": "position-human", "created_at": "2026-01-01T00:00:04Z",
            "body": "positioned", "path": "lib/a.rb", "line": 12,
        },
    ]


def test_ensure_description_only_writes_when_empty(tmp_path):
    log = tmp_path / "edits"
    template = tmp_path / "description.md"
    template.write_text("Template body\n", encoding="utf-8")
    write_cli(
        tmp_path,
        "gh",
        "import json, os, pathlib, sys\n"
        "a=sys.argv[1:]\n"
        "if a[:2] == ['pr','view']:\n"
        " print(json.dumps({'number':3,'url':'u','headRefOid':'s','headRefName':'b','body':os.environ.get('BODY','')}))\n"
        "elif a[:2] == ['pr','edit']:\n"
        " p=pathlib.Path(os.environ['LOG']); p.write_text((p.read_text() if p.exists() else '')+'edit\\n')\n"
        "else:\n sys.exit(2)\n",
    )
    base_env = {"PATH": cli_path(tmp_path), "LOG": str(log)}
    empty = payload(
        run_cli(
            ["ensure-description", "--platform", "github", "--template", str(template)],
            dict(base_env, BODY="   "),
        )
    )
    present = payload(
        run_cli(
            ["ensure-description", "--platform", "github", "--template", str(template)],
            dict(base_env, BODY="Already here"),
        )
    )
    assert empty == {"written": True}
    assert present == {"written": False}
    assert log.read_text(encoding="utf-8") == "edit\n"


GLAB_STUB = (
    "import json, os, pathlib, sys\n"
    "a=sys.argv[1:]\n"
    "if a[:2] == ['mr','view']:\n"
    " print(json.dumps({'iid':9,'sha':'abc','description':os.environ.get('DESC','')}))\n"
    "elif a and a[0] == 'api':\n"
    " i=a.index('--input') if '--input' in a else -1\n"
    " rec={'args':a,'input':pathlib.Path(a[i+1]).read_text() if i >= 0 else None}\n"
    " pathlib.Path(os.environ['LOG']).write_text(json.dumps(rec))\n"
    "else:\n sys.exit(2)\n"
)


def read_glab_call(log):
    call = json.loads(log.read_text(encoding="utf-8"))
    args = call["args"]
    assert "-f" not in args
    assert not any(item.startswith(("body=", "description=")) for item in args)
    assert args[args.index("--input") + 1] != ""
    assert args[args.index("-H") + 1] == "Content-Type: application/json"
    assert not os.path.exists(args[args.index("--input") + 1])
    return args, json.loads(call["input"])


def git_repo_with_remote(tmp_path, remote, url, branch="feat"):
    repo = tmp_path / "repo"
    repo.mkdir()
    for cmd in (
        ["git", "init", "-q"],
        ["git", "remote", "add", "origin", "https://gitlab.example.com/g/p.git"],
        ["git", "remote", "add", remote, url],
        ["git", "config", "branch.{0}.remote".format(branch), remote],
    ):
        subprocess.run(cmd, cwd=str(repo), check=True)
    return repo


def run_cli_in(repo, args, env):
    process_env = os.environ.copy()
    process_env.update(env)
    return subprocess.run(
        [PY, str(SCRIPT)] + args,
        cwd=str(repo),
        capture_output=True,
        universal_newlines=True,
        env=process_env,
    )


@pytest.mark.parametrize(
    "url,platform,cli",
    [
        ("https://github.com/o/r.git", "github", "gh"),
        ("https://git.example.com/o/r.git", "gitlab", "glab"),
    ],
)
def test_preflight_branch_uses_upstream_remote(tmp_path, url, platform, cli):
    repo = git_repo_with_remote(tmp_path, "upstream", url)
    result = payload(
        run_cli_in(repo, ["preflight", "--branch", "feat"], {"PATH": cli_path(tmp_path)})
    )
    assert result["platform"] == platform
    assert result["cli"] == cli
    assert result["branch"] == "feat"


def test_preflight_branch_without_config_falls_back_to_origin(tmp_path):
    repo = git_repo_with_remote(tmp_path, "upstream", "https://github.com/o/r.git")
    result = payload(
        run_cli_in(repo, ["preflight", "--branch", "other"], {"PATH": cli_path(tmp_path)})
    )
    assert result["platform"] == "gitlab"


def test_preflight_url_and_branch_are_exclusive(tmp_path):
    proc = run_cli(["preflight", "--url", "https://github.com/o/r", "--branch", "x"])
    assert payload(proc, expected_code=1)["error"]


def test_gitlab_comment_sends_json_input_file(tmp_path):
    log = tmp_path / "call.json"
    write_cli(tmp_path, "glab", GLAB_STUB)
    body_file = tmp_path / "body.md"
    text = 'Line "one" & more\n' + "long " * 5000 + "\n\u00e9\n"
    body_file.write_text(text, encoding="utf-8")
    result = payload(
        run_cli(
            ["comment", "--platform", "gitlab", "--body-file", str(body_file)],
            {"PATH": cli_path(tmp_path), "LOG": str(log)},
        )
    )
    assert result == {"posted": True}
    args, body = read_glab_call(log)
    assert args[:4] == ["api", "--method", "POST", "projects/:id/merge_requests/9/notes"]
    assert body == {"body": text}


def test_gitlab_ensure_description_sends_json_input_file(tmp_path):
    log = tmp_path / "call.json"
    write_cli(tmp_path, "glab", GLAB_STUB)
    template = tmp_path / "description.md"
    text = "## Summary\n" + "word " * 5000 + "\n"
    template.write_text(text, encoding="utf-8")
    result = payload(
        run_cli(
            ["ensure-description", "--platform", "gitlab", "--template", str(template)],
            {"PATH": cli_path(tmp_path), "LOG": str(log)},
        )
    )
    assert result == {"written": True}
    args, body = read_glab_call(log)
    assert args[:4] == ["api", "--method", "PUT", "projects/:id/merge_requests/9"]
    assert body == {"description": text}


def test_gitlab_set_section_sends_json_input_file(tmp_path):
    log = tmp_path / "call.json"
    write_cli(tmp_path, "glab", GLAB_STUB)
    section = tmp_path / "section.md"
    section.write_text("## AI Review Fixes\nnew " + "x" * 5000 + "\n", encoding="utf-8")
    result = payload(
        run_cli(
            ["set-section", "--platform", "gitlab", "--file", str(section)],
            {"PATH": cli_path(tmp_path), "LOG": str(log), "DESC": "Intro"},
        )
    )
    assert result == {"replaced": False}
    args, body = read_glab_call(log)
    assert args[:3] == ["api", "--method", "PUT"]
    assert body == {"description": "Intro\n\n## AI Review Fixes\nnew " + "x" * 5000 + "\n"}


GH_PUSH_STUB = (
    "import json, os, sys\n"
    "a=sys.argv[1:]\n"
    "if a[:2] == ['pr','view']:\n"
    " print(json.dumps({'number':3,'url':'u','headRefOid':'deadbeef','headRefName':'b','body':''}))\n"
    "elif a[0] == 'api' and a[1].endswith('/check-suites'):\n"
    " print(os.environ['SUITES'])\n"
    "elif a[0] == 'api' and a[1].endswith('/commits/deadbeef'):\n"
    " print(json.dumps({'commit':{'committer':{'date':'2026-01-01T00:00:05Z'}}}))\n"
    "else:\n sys.exit(2)\n"
)


def test_push_time_github_uses_earliest_check_suite(tmp_path):
    write_cli(tmp_path, "gh", GH_PUSH_STUB)
    suites = json.dumps(
        {
            "check_suites": [
                {"created_at": "2026-01-01T00:02:00Z"},
                {"created_at": "2026-01-01T00:01:00Z"},
            ]
        }
    )
    result = payload(
        run_cli(
            ["push-time", "--platform", "github"],
            {"PATH": cli_path(tmp_path), "SUITES": suites},
        )
    )
    assert result == {
        "head_sha": "deadbeef",
        "pushed_at": "2026-01-01T00:01:00Z",
        "source": "check_suite",
    }


def test_push_time_github_falls_back_to_commit_date(tmp_path):
    write_cli(tmp_path, "gh", GH_PUSH_STUB)
    result = payload(
        run_cli(
            ["push-time", "--platform", "github"],
            {"PATH": cli_path(tmp_path), "SUITES": json.dumps({"check_suites": []})},
        )
    )
    assert result == {
        "head_sha": "deadbeef",
        "pushed_at": "2026-01-01T00:00:05Z",
        "source": "commit_date",
    }


GLAB_PUSH_STUB = (
    "import json, os, sys\n"
    "a=sys.argv[1:]\n"
    "if a[:2] == ['mr','view']:\n"
    " mr={'iid':9,'sha':'cafe'}\n"
    " if os.environ.get('PIPE'): mr['head_pipeline']={'id':1,'sha':'cafe','created_at':os.environ['PIPE']}\n"
    " print(json.dumps(mr))\n"
    "elif a[0] == 'api' and a[1] == 'projects/:id/repository/commits/cafe':\n"
    " print(json.dumps({'committed_date':'2026-02-02T03:04:05.000+02:00'}))\n"
    "else:\n sys.exit(2)\n"
)


def test_push_time_gitlab_pipeline_and_fallback(tmp_path):
    write_cli(tmp_path, "glab", GLAB_PUSH_STUB)
    piped = payload(
        run_cli(
            ["push-time", "--platform", "gitlab"],
            {"PATH": cli_path(tmp_path), "PIPE": "2026-02-02T01:00:00.123Z"},
        )
    )
    assert piped == {
        "head_sha": "cafe",
        "pushed_at": "2026-02-02T01:00:00Z",
        "source": "pipeline",
    }
    fallback = payload(
        run_cli(["push-time", "--platform", "gitlab"], {"PATH": cli_path(tmp_path), "PIPE": ""})
    )
    assert fallback == {
        "head_sha": "cafe",
        "pushed_at": "2026-02-02T01:04:05Z",
        "source": "commit_date",
    }


def test_elapsed_minutes_between_timestamps():
    result = payload(
        run_cli(["elapsed", "--since", "2026-01-01T00:00:00Z", "--until", "2026-01-01T00:07:30Z"])
    )
    assert result == {"minutes": 7.5}


def test_elapsed_until_defaults_to_now():
    result = payload(run_cli(["elapsed", "--since", "2000-01-01T00:00:00Z"]))
    assert result["minutes"] > 0


def test_help_lists_all_subcommands():
    proc = subprocess.run([PY, str(SCRIPT), "--help"], capture_output=True, universal_newlines=True)
    assert proc.returncode == 0
    for name in (
        "preflight", "detect", "wait", "ensure-description", "fetch-review",
        "fetch-comments", "rerun-review", "parse", "record", "run-tests",
        "job-log", "comment", "set-section", "push-time", "elapsed",
    ):
        assert name in proc.stdout


def test_script_parses_as_python_37():
    source = SCRIPT.read_text(encoding="utf-8")
    try:
        ast.parse(source, feature_version=(3, 7))
    except TypeError:
        # Python 3.7 itself predates ast.parse(feature_version=...), but its
        # own parser is exactly the compatibility target.
        ast.parse(source)


# review-fix round: verdict, severity tags, job pick, states, push-time,
# self comments, review bot, stderr, empty checks


def test_parse_link_does_not_count_as_severity_tag():
    result = review_loop.parse_review("- **Low**: rename var, see [docs](https://x)\n")
    assert len(result["findings"]) == 1
    assert result["findings"][0]["severity"] == "low"
    assert result["findings"][0]["blocking"] is False
    assert result["blocking_count"] == 0


def test_parse_heading_severity_applies_unless_leading_tag_overrides():
    result = review_loop.parse_review(
        "### Low\n"
        "- rename var (see the High-level design) [Critical] later in text\n"
        "- [High] real override\n"
        "- #3 — **Medium**: numbered override\n"
    )
    assert [item["severity"] for item in result["findings"]] == ["low", "high", "medium"]
    assert result["blocking_count"] == 2


def test_parse_severity_label_anywhere_counts():
    result = review_loop.parse_review("- missing null check. Severity: High\n")
    assert result["findings"][0]["severity"] == "high"


def test_parse_not_lgtm_is_not_lgtm():
    assert review_loop.parse_review("Not LGTM\n")["verdict"] == "unknown"
    assert review_loop.parse_review("This is not LGTM yet.\n")["verdict"] == "unknown"


@pytest.mark.parametrize(
    "text",
    [
        "LGTM pending fixes\n",
        "LGTM once the tests pass\n",
        "LGTM after you rename it\n",
        "LGTM except for the cache\n",
        "LGTM, but fix the race\n",
        "LGTM if CI is green\n",
    ],
)
def test_parse_conditional_lgtm_is_not_lgtm(text):
    assert review_loop.parse_review(text)["verdict"] == "unknown"


def test_parse_plain_lgtm_sentence_still_lgtm():
    assert review_loop.parse_review("Overall LGTM. Nice work.\n")["verdict"] == "lgtm"


def test_parse_priority_tags():
    result = review_loop.parse_review(
        "- [P0] crash\n- [P1] data loss\n- [P2] slow path\n- [P3] naming\n- [P4] typo\n"
    )
    assert [item["severity"] for item in result["findings"]] == ["p0", "p1", "p2", "p3", "p4"]
    assert [item["blocking"] for item in result["findings"]] == [True, True, True, False, False]
    assert result["blocking_count"] == 3


def test_parse_p3_only_is_nonblocking():
    result = review_loop.parse_review("- [P3] naming nit\n")
    assert len(result["findings"]) == 1
    assert result["findings"][0]["blocking"] is False
    assert result["blocking_count"] == 0
    assert result["verdict"] == "unknown"


def test_parse_prose_request_changes_without_findings():
    result = review_loop.parse_review("Request changes: the retry logic is unsafe.\n")
    assert result["verdict"] == "changes"
    assert result["findings"] == []


def test_job_pick_uses_pattern_priority_not_list_order():
    summary = review_loop.summarize_checks(
        [
            {"name": "Dependency Review", "bucket": "pass"},
            {"name": "ai-code-review", "bucket": "fail"},
        ]
    )
    assert summary["review_job"] == "ai-code-review"
    assert summary["failed_jobs"] == []


def test_job_pick_exact_job_wins_over_priority():
    summary = review_loop.summarize_checks(
        [
            {"name": "ai-code-review", "bucket": "pass"},
            {"name": "Dependency Review", "bucket": "pass"},
        ],
        job="Dependency Review",
    )
    assert summary["review_job"] == "Dependency Review"


@pytest.mark.parametrize(
    "state",
    [
        "created", "pending", "running", "waiting_for_resource",
        "preparing", "scheduled", "canceling",
    ],
)
def test_gitlab_in_flight_states_are_running(state):
    summary = review_loop.summarize_checks([{"name": "ai-review", "status": state}])
    assert summary["status"] == "running"


def test_gitlab_wait_waiting_for_resource_is_running(tmp_path):
    write_cli(
        tmp_path,
        "glab",
        "import json, sys\n"
        "a=sys.argv[1:]\n"
        "if a[:2] == ['mr','view']:\n print(json.dumps({'iid':9,'head_pipeline':{'id':44}}))\n"
        "elif a and a[0] == 'api':\n print(json.dumps([{'name':'ai-review','status':'waiting_for_resource'}]))\n"
        "else:\n sys.exit(2)\n",
    )
    result = payload(
        run_cli(
            ["wait", "--platform", "gitlab", "--minutes", "0", "--max-extensions", "1"],
            {"PATH": cli_path(tmp_path)},
        )
    )
    assert result["status"] == "running"
    assert result["extensions"] == 1


GLAB_STALE_STUB = (
    "import json, os, pathlib, sys\n"
    "a=sys.argv[1:]\n"
    "if a[:2] == ['mr','view']:\n"
    " p=pathlib.Path(os.environ['COUNTER'])\n"
    " n=int(p.read_text())+1 if p.exists() else 1\n"
    " p.write_text(str(n))\n"
    " fresh=int(os.environ.get('FRESH_AT','0'))\n"
    " sha='cafe' if fresh and n >= fresh else 'old1'\n"
    " print(json.dumps({'iid':9,'sha':'cafe','head_pipeline':{'id':1,'sha':sha,"
    "'created_at':'2026-02-02T01:00:00Z'}}))\n"
    "elif a[0] == 'api' and a[1] == 'projects/:id/repository/commits/cafe':\n"
    " print(json.dumps({'committed_date':'2026-02-02T03:04:05.000+02:00'}))\n"
    "else:\n sys.exit(2)\n"
)


def test_push_time_gitlab_stale_pipeline_retries_then_falls_back(tmp_path):
    counter = tmp_path / "views"
    write_cli(tmp_path, "glab", GLAB_STALE_STUB)
    result = payload(
        run_cli(
            ["push-time", "--platform", "gitlab"],
            {"PATH": cli_path(tmp_path), "COUNTER": str(counter)},
        )
    )
    assert result == {
        "head_sha": "cafe",
        "pushed_at": "2026-02-02T01:04:05Z",
        "source": "commit_date",
    }
    assert counter.read_text() == "7"


def test_push_time_gitlab_stale_pipeline_then_fresh(tmp_path):
    counter = tmp_path / "views"
    write_cli(tmp_path, "glab", GLAB_STALE_STUB)
    result = payload(
        run_cli(
            ["push-time", "--platform", "gitlab"],
            {"PATH": cli_path(tmp_path), "COUNTER": str(counter), "FRESH_AT": "3"},
        )
    )
    assert result["source"] == "pipeline"
    assert result["pushed_at"] == "2026-02-02T01:00:00Z"
    assert counter.read_text() == "3"


def test_fetch_review_excludes_self_comments_github(tmp_path):
    gh_rest_cli(
        tmp_path,
        issue=[
            rest("bot[bot]", "Review: [High] bug", "2026-01-01T00:00:01Z", "Bot"),
            rest("me", "Review reply: not a bug", "2026-01-01T00:00:05Z"),
        ],
    )
    result = payload(
        run_cli(
            ["fetch-review", "--platform", "github", "--since", "2026-01-01T00:00:00Z", "--retries", "0"],
            {"PATH": cli_path(tmp_path)},
        )
    )
    assert result["author"] == "bot[bot]"
    assert result["body"] == "Review: [High] bug"


def test_fetch_review_excludes_self_comments_gitlab(tmp_path):
    write_cli(
        tmp_path,
        "glab",
        "import json, sys\n"
        "a=sys.argv[1:]\n"
        "if a[:2] == ['mr','view']:\n print(json.dumps({'iid':9,'sha':'abc'}))\n"
        "elif a[:2] == ['api','user']:\n print(json.dumps({'username':'me'}))\n"
        "elif a and a[0] == 'api':\n"
        " print(json.dumps(["
        "{'author':{'username':'me'},'body':'Review reply','created_at':'2026-01-01T00:00:05Z'},"
        "{'author':{'username':'bot','bot':True},'body':'Review LGTM','created_at':'2026-01-01T00:00:01Z'}]))\n"
        "else:\n sys.exit(2)\n",
    )
    result = payload(
        run_cli(
            ["fetch-review", "--platform", "gitlab", "--since", "2026-01-01T00:00:00Z", "--retries", "0"],
            {"PATH": cli_path(tmp_path)},
        )
    )
    assert result["author"] == "bot"


def test_pick_latest_comment_exclude():
    comments = [
        {"author": {"login": "me"}, "body": "review", "created_at": "2026-01-01T00:00:05Z"},
        {"author": {"login": "bot"}, "body": "review", "created_at": "2026-01-01T00:00:01Z"},
    ]
    found = review_loop.pick_latest_comment(
        comments, "2026-01-01T00:00:00Z", exclude=("me",)
    )
    assert found["author"] == "bot"


def test_record_bot_writes_and_shows(tmp_path):
    agents = tmp_path / "AGENTS.md"
    agents.write_text("## Review loop\n- ci-wait-minutes: 7\n", encoding="utf-8")
    first = payload(run_cli(["record", "--agents", str(agents), "--bot", "review-bot[bot]"]))
    assert first["bot_written"] is True
    assert first["review_bot"] == "review-bot[bot]"
    assert first["minutes_written"] is False
    assert agents.read_text(encoding="utf-8") == (
        "## Review loop\n- ci-wait-minutes: 7\n- review-bot: review-bot[bot]\n"
    )
    again = payload(run_cli(["record", "--agents", str(agents), "--bot", "review-bot[bot]"]))
    assert again["bot_written"] is False
    shown = payload(run_cli(["record", "--agents", str(agents), "--show"]))
    assert shown["review_bot"] == "review-bot[bot]"
    assert shown["ci_wait_minutes"] == 7


def test_cli_error_includes_redacted_stderr_tail(tmp_path):
    secret_gh = "ghp_" + "A" * 36
    secret_gl = "glpat-" + "b" * 20
    write_cli(
        tmp_path,
        "gh",
        "import sys\n"
        "sys.stderr.write('x' * 600 + ' token " + secret_gh + " and " + secret_gl + " end\\n')\n"
        "sys.exit(4)\n",
    )
    result = payload(
        run_cli(["detect", "--platform", "github"], {"PATH": cli_path(tmp_path)}),
        expected_code=1,
    )
    assert "exit 4" in result["error"]
    assert len(result["stderr"]) <= 500
    assert secret_gh not in result["stderr"]
    assert secret_gl not in result["stderr"]
    assert "[REDACTED]" in result["stderr"]
    assert result["stderr"].rstrip().endswith("end")


@pytest.mark.parametrize("stdout", ["", "no checks reported on the 'feat' branch"])
def test_wait_github_no_checks_is_none(tmp_path, stdout):
    write_cli(
        tmp_path,
        "gh",
        "import sys\n"
        "sys.stdout.write(" + repr(stdout) + ")\n"
        "sys.stderr.write('no checks reported\\n')\n"
        "sys.exit(1)\n",
    )
    result = payload(
        run_cli(["wait", "--platform", "github", "--minutes", "0"], {"PATH": cli_path(tmp_path)})
    )
    assert result["status"] == "none"
    assert result["review_job"] is None


@pytest.mark.parametrize("heading", ["## No high-severity issues", "### Error handling"])
def test_parse_heading_must_start_with_severity(heading):
    result = review_loop.parse_review(heading + "\n- consider renaming\n- [Low] typo\n")
    assert [item["severity"] for item in result["findings"]] == ["low"]
    assert result["blocking_count"] == 0


@pytest.mark.parametrize(
    "heading, severity",
    [
        ("### Critical (2)", "critical"),
        ("#### \U0001F534 High", "high"),
        ("### **Warning**", "warning"),
        ("### P1: correctness", "p1"),
        ("### Low: polish", "low"),
        ("### Critical Issues (2)", "critical"),
    ],
)
def test_parse_heading_leading_severity_still_applies(heading, severity):
    result = review_loop.parse_review(heading + "\n- something to fix\n")
    assert [item["severity"] for item in result["findings"]] == [severity]


def test_parse_no_high_severity_heading_with_lgtm_is_lgtm():
    result = review_loop.parse_review(
        "## No high-severity issues\n- tidy code\n- good tests\n\nLGTM\n"
    )
    assert result["verdict"] == "lgtm"
    assert result["blocking_count"] == 0


@pytest.mark.parametrize(
    "text",
    [
        "This is not quite LGTM.\n",
        "Not yet LGTM, see below.\n",
        "It isn't LGTM until the race is fixed.\n",
        "Not really LGTM.\n",
        "This change is not, in its current form, LGTM.\n",
    ],
)
def test_parse_hedged_negated_lgtm_is_not_lgtm(text):
    assert review_loop.parse_review(text)["verdict"] == "unknown"


def test_parse_negation_in_previous_sentence_does_not_block_lgtm():
    assert review_loop.parse_review("No issues found. LGTM\n")["verdict"] == "lgtm"


def test_redact_fine_grained_github_pat():
    secret = "github_pat_" + "A1b2_" * 10
    redacted = review_loop.redact_stderr("token " + secret + " end")
    assert secret not in redacted
    assert "[REDACTED]" in redacted


@pytest.mark.parametrize("stdout", ["", "  \n"])
def test_wait_github_exit_zero_empty_stdout_is_none(tmp_path, stdout):
    write_cli(
        tmp_path,
        "gh",
        "import sys\nsys.stdout.write(" + repr(stdout) + ")\nsys.exit(0)\n",
    )
    result = payload(
        run_cli(["wait", "--platform", "github", "--minutes", "0"], {"PATH": cli_path(tmp_path)})
    )
    assert result["status"] == "none"
    assert result["review_job"] is None


# local test queue


QUEUE_COMMAND = (
    "import json, pathlib, sys, time\n"
    "start=time.time()\n"
    "time.sleep(float(sys.argv[3]))\n"
    "pathlib.Path(sys.argv[1]).write_text(json.dumps({'label':sys.argv[2],"
    "'start':start,'end':time.time()}))\n"
)


FIFO_COMMAND = (
    "import pathlib, sys, time\n"
    "with pathlib.Path(sys.argv[1]).open('a') as handle:\n"
    " handle.write(sys.argv[2]+'\\n')\n"
    " handle.flush()\n"
    "time.sleep(float(sys.argv[3]))\n"
)


def start_run_tests(repo, queue, command, timeout="5"):
    local_settings = repo / "AGENTS.local.md"
    if not local_settings.exists():
        local_settings.write_text("## Review loop\n- tests: serial\n", encoding="utf-8")
    env = os.environ.copy()
    env.update({"TLOR_TEST_QUEUE_DIR": str(queue), "REVIEW_LOOP_SLEEP_SCALE": "0.01"})
    return subprocess.Popen(
        [PY, str(SCRIPT), "run-tests", "--cmd", command, "--timeout", timeout],
        cwd=str(repo),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
        env=env,
    )


def wait_for_ticket_count(queue, count):
    deadline = time.time() + 5
    while time.time() < deadline:
        if len(list(queue.glob("ticket-*.json"))) >= count:
            return
        time.sleep(0.01)
    raise AssertionError("queue did not reach {0} tickets".format(count))


def command_string(*parts):
    return " ".join(shlex.quote(str(part)) for part in parts)


def popen_payload(proc, expected_code=0):
    stdout, stderr = proc.communicate(timeout=10)
    assert proc.returncode == expected_code, stdout + stderr
    assert len(stdout.splitlines()) == 1
    return json.loads(stdout)


def test_run_tests_serializes_two_concurrent_processes(tmp_path):
    repo = tmp_path / "repo"
    queue = tmp_path / "queue"
    repo.mkdir()
    runner = write_cli(tmp_path, "timed.py", QUEUE_COMMAND)
    outputs = [tmp_path / "one.json", tmp_path / "two.json"]
    first = start_run_tests(repo, queue, command_string(PY, runner, outputs[0], "one", "1"))
    wait_for_ticket_count(queue, 1)
    second = start_run_tests(repo, queue, command_string(PY, runner, outputs[1], "two", "1"))
    assert popen_payload(first)["status"] == "ok"
    assert popen_payload(second)["status"] == "ok"
    intervals = [json.loads(path.read_text(encoding="utf-8")) for path in outputs]
    assert intervals[0]["end"] <= intervals[1]["start"]


def test_run_tests_queue_is_fifo_for_three_tickets(tmp_path):
    repo = tmp_path / "repo"
    queue = tmp_path / "queue"
    order = tmp_path / "order.txt"
    repo.mkdir()
    runner = write_cli(tmp_path, "fifo.py", FIFO_COMMAND)
    processes = []
    for index, label in enumerate(("first", "second", "third"), 1):
        processes.append(
            start_run_tests(repo, queue, command_string(PY, runner, order, label, "0.3"))
        )
        wait_for_ticket_count(queue, index)
    for proc in processes:
        assert popen_payload(proc)["status"] == "ok"
    assert order.read_text(encoding="utf-8").splitlines() == ["first", "second", "third"]


def test_run_tests_clears_stale_lock_with_dead_pid_and_uses_recorded_command(tmp_path):
    repo = tmp_path / "repo"
    queue = tmp_path / "queue"
    marker = tmp_path / "ran.json"
    repo.mkdir()
    queue.mkdir()
    (queue / "lock").write_text("99999999", encoding="utf-8")
    runner = write_cli(tmp_path, "recorded.py", QUEUE_COMMAND)
    (repo / "AGENTS.md").write_text(
        "## Review loop\n- test-command: {0}\n".format(
            command_string(PY, runner, marker, "recorded", "0")
        ),
        encoding="utf-8",
    )
    (repo / "AGENTS.local.md").write_text(
        "## Review loop\n- tests: serial\n", encoding="utf-8"
    )
    proc = run_cli_in(
        repo,
        ["run-tests"],
        {"TLOR_TEST_QUEUE_DIR": str(queue), "REVIEW_LOOP_SLEEP_SCALE": "0"},
    )
    result = payload(proc)
    assert result["status"] == "ok"
    assert marker.exists()
    assert not (queue / "lock").exists()


def test_run_tests_times_out_behind_live_lock_without_running(tmp_path):
    repo = tmp_path / "repo"
    queue = tmp_path / "queue"
    marker = tmp_path / "should-not-exist"
    repo.mkdir()
    queue.mkdir()
    (repo / "AGENTS.local.md").write_text(
        "## Review loop\n- tests: serial\n", encoding="utf-8"
    )
    (queue / "lock").write_text(str(os.getpid()), encoding="utf-8")
    command = command_string(PY, "-c", "import pathlib;pathlib.Path({0!r}).touch()".format(str(marker)))
    proc = run_cli_in(
        repo,
        ["run-tests", "--cmd", command, "--timeout", "0.05"],
        {"TLOR_TEST_QUEUE_DIR": str(queue), "REVIEW_LOOP_SLEEP_SCALE": "0.01"},
    )
    assert payload(proc, expected_code=1) == {"status": "timeout"}
    assert not marker.exists()
    assert not list(queue.glob("ticket-*.json"))


def test_run_tests_refuses_when_local_policy_is_never(tmp_path):
    repo = tmp_path / "repo"
    queue = tmp_path / "queue"
    marker = tmp_path / "should-not-exist"
    repo.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=str(repo), check=True)
    (repo / "AGENTS.local.md").write_text(
        "## Review loop\n- tests: never\n", encoding="utf-8"
    )
    command = command_string(PY, "-c", "import pathlib;pathlib.Path({0!r}).touch()".format(str(marker)))
    proc = run_cli_in(
        repo,
        ["run-tests", "--cmd", command],
        {"TLOR_TEST_QUEUE_DIR": str(queue), "REVIEW_LOOP_SLEEP_SCALE": "0"},
    )
    result = payload(proc, expected_code=1)
    assert "never" in result["error"]
    assert not marker.exists()
    assert not queue.exists()


# failed CI logs


GH_JOB_LINK = "https://github.com/o/r/actions/runs/123/job/456"


def gh_job_log_cli(tmp_path, checks, log_failed, full_log="", view_exit=0):
    write_cli(
        tmp_path,
        "gh",
        "import json, sys\n"
        "a=sys.argv[1:]\n"
        "if a[:2] == ['pr','checks']:\n"
        " assert 'name,link,state' in a[-1] or 'link' in a[-1], a\n"
        " print(json.dumps(" + repr(checks) + "))\n"
        "elif a[:3] == ['run','view','123'] and '--job' in a and a[a.index('--job')+1] == '456':\n"
        " if '--log-failed' in a:\n"
        "  sys.stdout.write(" + repr(log_failed) + ")\n"
        " elif '--log' in a:\n"
        "  sys.stdout.write(" + repr(full_log) + ")\n"
        " sys.exit(" + repr(view_exit) + ")\n"
        "else:\n sys.exit(2)\n",
    )


def test_rerun_review_github_calls_run_rerun_and_returns_since(tmp_path):
    log = tmp_path / "calls"
    write_cli(
        tmp_path,
        "gh",
        "import json, os, pathlib, sys\n"
        "a=sys.argv[1:]\n"
        "p=pathlib.Path(os.environ['LOG'])\n"
        "p.write_text((p.read_text() if p.exists() else '')+json.dumps(a)+'\\n')\n"
        "if a[:2] == ['pr','checks']:\n"
        " print(json.dumps([{'name':'AI Review','state':'SUCCESS','bucket':'pass','link':"
        + repr(GH_JOB_LINK) + "}]))\n"
        "elif a == ['run','rerun','123','--job','456']:\n pass\n"
        "else:\n sys.exit(2)\n",
    )
    result = payload(
        run_cli(
            ["rerun-review", "--platform", "github", "--pr", "7", "--job", "AI Review"],
            {"PATH": cli_path(tmp_path), "LOG": str(log)},
        )
    )
    calls = [json.loads(line) for line in log.read_text(encoding="utf-8").splitlines()]
    assert calls[-1] == ["run", "rerun", "123", "--job", "456"]
    assert result["job"] == "AI Review"
    assert result["since"].endswith("Z")
    assert review_loop.parse_utc_timestamp(result["since"]).tzinfo is not None


def test_rerun_review_gitlab_posts_retry(tmp_path):
    log = tmp_path / "retry-call"
    write_cli(
        tmp_path,
        "glab",
        "import json, os, pathlib, sys\n"
        "a=sys.argv[1:]\n"
        "if a[:2] == ['mr','view']:\n print(json.dumps({'iid':9,'head_pipeline':{'id':44}}))\n"
        "elif a == ['api','projects/:id/pipelines/44/jobs?per_page=100']:\n"
        " print(json.dumps([{'id':55,'name':'ai-review','status':'success'}]))\n"
        "elif a == ['api','-X','POST','projects/:id/jobs/55/retry']:\n"
        " pathlib.Path(os.environ['LOG']).write_text(json.dumps(a))\n"
        "else:\n sys.exit(2)\n",
    )
    result = payload(
        run_cli(
            ["rerun-review", "--platform", "gitlab", "--pr", "9"],
            {"PATH": cli_path(tmp_path), "LOG": str(log)},
        )
    )
    assert json.loads(log.read_text(encoding="utf-8")) == [
        "api", "-X", "POST", "projects/:id/jobs/55/retry",
    ]
    assert result["job"] == "ai-review"
    assert result["since"].endswith("Z")


def test_rerun_review_no_job_does_not_call_rerun(tmp_path):
    log = tmp_path / "calls"
    write_cli(
        tmp_path,
        "gh",
        "import json, os, pathlib, sys\n"
        "a=sys.argv[1:]\n"
        "p=pathlib.Path(os.environ['LOG'])\n"
        "p.write_text((p.read_text() if p.exists() else '')+json.dumps(a)+'\\n')\n"
        "if a[:2] == ['pr','checks']:\n print(json.dumps([{'name':'lint','state':'SUCCESS','bucket':'pass'}]))\n"
        "else:\n sys.exit(2)\n",
    )
    proc = run_cli(
        ["rerun-review", "--platform", "github", "--job", "AI Review"],
        {"PATH": cli_path(tmp_path), "LOG": str(log)},
    )
    assert proc.returncode != 0
    assert "review job not found" in proc.stdout
    calls = [json.loads(line) for line in log.read_text(encoding="utf-8").splitlines()]
    assert all(call[:2] != ["run", "rerun"] for call in calls)


def test_rerun_review_cli_failure_is_error(tmp_path):
    write_cli(
        tmp_path,
        "gh",
        "import json, sys\n"
        "a=sys.argv[1:]\n"
        "if a[:2] == ['pr','checks']:\n"
        " print(json.dumps([{'name':'AI Review','state':'SUCCESS','bucket':'pass','link':"
        + repr(GH_JOB_LINK) + "}]))\n"
        "elif a[:2] == ['run','rerun']:\n print('cannot rerun', file=sys.stderr)\n sys.exit(7)\n"
        "else:\n sys.exit(2)\n",
    )
    proc = run_cli(
        ["rerun-review", "--platform", "github", "--job-pattern", "AI Review"],
        {"PATH": cli_path(tmp_path)},
    )
    assert proc.returncode != 0
    assert "gh command failed (exit 7)" in proc.stdout


def test_job_log_github_tail_and_redaction(tmp_path):
    secret = "ghp_" + "A" * 36
    gh_job_log_cli(
        tmp_path,
        [{"name": "Unit tests", "state": "FAILURE", "link": GH_JOB_LINK}],
        "old\nsecret " + secret + "\nlast\n",
    )
    result = payload(
        run_cli(
            ["job-log", "--platform", "github", "--job", "Unit tests", "--lines", "2"],
            {"PATH": cli_path(tmp_path)},
        )
    )
    assert result == {"job": "Unit tests", "log_tail": "secret [REDACTED]\nlast", "empty": False}


def test_job_log_github_falls_back_to_full_log_when_failed_log_empty(tmp_path):
    gh_job_log_cli(
        tmp_path,
        [{"name": "build", "state": "FAILURE", "link": GH_JOB_LINK}],
        "",
        full_log="one\ntwo\n",
    )
    result = payload(
        run_cli(["job-log", "--platform", "github", "--job", "build"], {"PATH": cli_path(tmp_path)})
    )
    assert result == {"job": "build", "log_tail": "one\ntwo", "empty": False}


def test_job_log_github_non_actions_check_is_error(tmp_path):
    gh_job_log_cli(
        tmp_path,
        [{"name": "ext", "state": "FAILURE", "link": "https://ci.example.com/build/9"}],
        "unused",
    )
    result = payload(
        run_cli(["job-log", "--platform", "github", "--job", "ext"], {"PATH": cli_path(tmp_path)}),
        expected_code=1,
    )
    assert "not a GitHub Actions job" in result["error"]


def test_job_log_github_unknown_job_is_error(tmp_path):
    gh_job_log_cli(
        tmp_path,
        [{"name": "build", "state": "FAILURE", "link": GH_JOB_LINK}],
        "unused",
    )
    result = payload(
        run_cli(["job-log", "--platform", "github", "--job", "nope"], {"PATH": cli_path(tmp_path)}),
        expected_code=1,
    )
    assert "failed job not found" in result["error"]


def test_wait_reports_canceled_non_review_jobs(tmp_path):
    write_cli(
        tmp_path,
        "gh",
        "import json, sys\n"
        "if sys.argv[1:3] == ['pr', 'checks']:\n"
        " print(json.dumps([{'name':'AI Code Review','state':'SUCCESS','bucket':'pass'},"
        "{'name':'lint','state':'CANCELLED','bucket':'cancel'}]))\n"
        " sys.exit(1)\n"
        "sys.exit(2)\n",
    )
    result = payload(
        run_cli(["wait", "--platform", "github", "--minutes", "1"], {"PATH": cli_path(tmp_path)})
    )
    assert result["status"] == "canceled"
    assert result["failed_jobs"] == []
    assert result["canceled_jobs"] == ["lint"]


def test_summarize_checks_canceled_jobs_exclude_review_job():
    checks = [
        {"name": "ai-code-review", "status": "canceled"},
        {"name": "lint", "status": "failed"},
    ]
    summary = review_loop.summarize_checks(checks)
    assert summary["canceled_jobs"] == []
    assert summary["failed_jobs"] == ["lint"]
    assert review_loop.summarize_checks([])["canceled_jobs"] == []


def test_record_max_rounds_written_true_when_adding_default_value(tmp_path):
    agents = tmp_path / "AGENTS.md"
    agents.write_text("## Review loop\n- ci-wait-minutes: 5\n", encoding="utf-8")
    result = payload(run_cli(["record", "--agents", str(agents), "--max-rounds", "10"]))
    assert result["max_rounds_written"] is True
    assert "- max-rounds: 10" in agents.read_text(encoding="utf-8")
    again = payload(run_cli(["record", "--agents", str(agents), "--max-rounds", "10"]))
    assert again["max_rounds_written"] is False


def test_job_log_gitlab_uses_mr_head_pipeline_job(tmp_path):
    secret = "glpat-" + "b" * 20
    write_cli(
        tmp_path,
        "glab",
        "import json, sys\n"
        "a=sys.argv[1:]\n"
        "if a[:2] == ['mr','view']:\n print(json.dumps({'iid':9,'head_pipeline':{'id':44}}))\n"
        "elif a and a[0] == 'api':\n"
        " print(json.dumps([{'id':55,'name':'lint','status':'failed'}]))\n"
        "elif a[:3] == ['ci','trace','55']:\n"
        " print('discard\\nline " + secret + "\\nfinal')\n"
        "else:\n sys.exit(2)\n",
    )
    result = payload(
        run_cli(
            ["job-log", "--platform", "gitlab", "--job", "lint", "--lines", "2"],
            {"PATH": cli_path(tmp_path)},
        )
    )
    assert result == {"job": "lint", "log_tail": "line [REDACTED]\nfinal", "empty": False}


@pytest.mark.parametrize("state", ["manual", "skipped"])
def test_gitlab_manual_and_skipped_are_explicitly_not_failed(state):
    check = {"name": "optional", "status": state}
    assert review_loop._check_category(check) == "success"
    summary = review_loop.summarize_checks([check])
    assert summary["status"] == "success"
    assert summary["failed_jobs"] == []


# review-fix round 2: shell command lines, live-holder exclusion, atomic queue
# files, repo-root settings, record --local, allow_failure


def serial_repo(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "AGENTS.local.md").write_text("## Review loop\n- tests: serial\n", encoding="utf-8")
    return repo


def queue_env(queue, scale="0.01"):
    return {"TLOR_TEST_QUEUE_DIR": str(queue), "REVIEW_LOOP_SLEEP_SCALE": scale}


@pytest.mark.parametrize("command,status", [
    ("cd . && false", "failed"),
    ("true && false", "failed"),
    ("CI=1 true", "ok"),
    ("cd . && true", "ok"),
])
def test_run_tests_runs_command_line_through_sh(tmp_path, command, status):
    repo = serial_repo(tmp_path)
    proc = run_cli_in(repo, ["run-tests", "--cmd", command], queue_env(tmp_path / "queue", "0"))
    result = payload(proc, expected_code=0 if status == "ok" else 1)
    assert result["status"] == status
    assert (result["exit_code"] == 0) == (status == "ok")


def backdate(path, seconds):
    stamp = time.time() - seconds
    os.utime(str(path), (stamp, stamp))


def test_run_tests_never_purges_live_lock_however_old(tmp_path):
    repo = serial_repo(tmp_path)
    queue = tmp_path / "queue"
    queue.mkdir()
    marker = tmp_path / "should-not-exist"
    lock = queue / "lock"
    lock.write_text(json.dumps({"pid": os.getpid()}), encoding="utf-8")
    backdate(lock, 3 * 24 * 3600)
    proc = run_cli_in(
        repo,
        ["run-tests", "--cmd", "touch " + shlex.quote(str(marker)), "--timeout", "0.2"],
        queue_env(queue),
    )
    assert payload(proc, expected_code=1) == {"status": "timeout"}
    assert not marker.exists()
    assert lock.exists()


def test_purge_removes_dead_lock_only_for_queue_head(tmp_path):
    queue = tmp_path / "queue"
    queue.mkdir()
    head = queue / "ticket-{0:020d}-{1}.json".format(1, os.getpid())
    tail = queue / "ticket-{0:020d}-{1}.json".format(2, os.getpid())
    for ticket in (head, tail):
        ticket.write_text(json.dumps({"pid": os.getpid()}), encoding="utf-8")
    lock = queue / "lock"
    lock.write_text(json.dumps({"pid": 99999999}), encoding="utf-8")
    review_loop._purge_stale_queue_files(queue, tail)
    assert lock.exists()
    review_loop._purge_stale_queue_files(queue, None)
    assert lock.exists()
    review_loop._purge_stale_queue_files(queue, head)
    assert not lock.exists()


def test_run_tests_never_purges_live_ticket_however_old(tmp_path):
    repo = serial_repo(tmp_path)
    queue = tmp_path / "queue"
    queue.mkdir()
    marker = tmp_path / "should-not-exist"
    ticket = queue / "ticket-{0:020d}-{1}.json".format(1, os.getpid())
    ticket.write_text(json.dumps({"pid": os.getpid()}), encoding="utf-8")
    backdate(ticket, 3 * 24 * 3600)
    proc = run_cli_in(
        repo,
        ["run-tests", "--cmd", "touch " + shlex.quote(str(marker)), "--timeout", "0.2"],
        queue_env(queue),
    )
    assert payload(proc, expected_code=1) == {"status": "timeout"}
    assert not marker.exists()
    assert ticket.exists()


def test_run_tests_unreadable_lock_kept_during_grace_then_purged(tmp_path):
    repo = serial_repo(tmp_path)
    queue = tmp_path / "queue"
    queue.mkdir()
    marker = tmp_path / "ran"
    lock = queue / "lock"
    lock.write_text("", encoding="utf-8")
    command = "touch " + shlex.quote(str(marker))
    fresh = run_cli_in(repo, ["run-tests", "--cmd", command, "--timeout", "0.2"], queue_env(queue))
    assert payload(fresh, expected_code=1) == {"status": "timeout"}
    assert not marker.exists()
    backdate(lock, 31)
    old = run_cli_in(repo, ["run-tests", "--cmd", command, "--timeout", "0.2"], queue_env(queue))
    assert payload(old)["status"] == "ok"
    assert marker.exists()


def test_run_tests_lock_holds_pid_json_and_leaves_no_temp_files(tmp_path):
    repo = serial_repo(tmp_path)
    queue = tmp_path / "queue"
    proc = run_cli_in(repo, ["run-tests", "--cmd", 'cat "$TLOR_TEST_QUEUE_DIR/lock"'], queue_env(queue, "0"))
    result = payload(proc)
    assert isinstance(json.loads(result["stdout_tail"])["pid"], int)
    assert sorted(path.name for path in queue.iterdir()) == []


def test_write_exclusive_never_overwrites_and_cleans_temp(tmp_path):
    target = tmp_path / "lock"
    assert review_loop._write_exclusive(target, '{"pid":1}') is True
    assert review_loop._write_exclusive(target, '{"pid":2}') is False
    assert target.read_text(encoding="utf-8") == '{"pid":1}'
    assert [path.name for path in tmp_path.iterdir()] == ["lock"]


def test_run_tests_reads_settings_from_repo_root_and_runs_in_cwd(tmp_path):
    repo = serial_repo(tmp_path)
    subprocess.run(["git", "init", "-q"], cwd=str(repo), check=True)
    sub = repo / "sub" / "deep"
    sub.mkdir(parents=True)
    (repo / "AGENTS.md").write_text("## Review loop\n- test-command: pwd\n", encoding="utf-8")
    result = payload(run_cli_in(sub, ["run-tests"], queue_env(tmp_path / "queue", "0")))
    assert result["status"] == "ok"
    assert os.path.realpath(result["stdout_tail"].strip()) == os.path.realpath(str(sub))


def test_record_local_without_tests_is_error_and_writes_nothing(tmp_path):
    agents = tmp_path / "AGENTS.md"
    proc = run_cli(["record", "--agents", str(agents), "--local"])
    assert "--tests" in payload(proc, expected_code=1)["error"]
    assert not (tmp_path / "AGENTS.local.md").exists()
    assert not agents.exists()


def test_summarize_checks_ignores_allow_failure_jobs():
    checks = [
        {"name": "ai-review", "status": "success"},
        {"name": "lint", "status": "failed", "allow_failure": True},
        {"name": "docs", "status": "canceled", "allow_failure": True},
        {"name": "unit", "status": "failed", "allow_failure": False},
    ]
    summary = review_loop.summarize_checks(checks)
    assert summary["failed_jobs"] == ["unit"]
    assert summary["canceled_jobs"] == []
    only_allowed = review_loop.summarize_checks(checks[:3])
    assert only_allowed["status"] == "success"
    assert only_allowed["failed_jobs"] == [] and only_allowed["canceled_jobs"] == []


def test_gitlab_wait_allow_failure_job_is_not_failed(tmp_path):
    write_cli(
        tmp_path,
        "glab",
        "import json, sys\n"
        "a=sys.argv[1:]\n"
        "if a[:2] == ['mr','view']:\n print(json.dumps({'iid':9,'head_pipeline':{'id':44}}))\n"
        "elif a and a[0] == 'api':\n print(json.dumps(["
        "{'name':'ai-review','status':'success','allow_failure':False},"
        "{'name':'audit','status':'failed','allow_failure':True}]))\n"
        "else:\n sys.exit(2)\n",
    )
    result = payload(
        run_cli(["wait", "--platform", "gitlab", "--minutes", "0"], {"PATH": cli_path(tmp_path)})
    )
    assert result["status"] == "success"
    assert result["failed_jobs"] == [] and result["canceled_jobs"] == []


def _pid_alive(pid):
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def test_run_tests_sigterm_kills_child_group_before_lock_release(tmp_path):
    import signal

    repo = tmp_path / "repo"
    queue = tmp_path / "queue"
    repo.mkdir()
    pidfile = tmp_path / "child.pid"
    marker = tmp_path / "end.marker"
    command = "echo $$ > {0}; sleep 5; touch {1}".format(
        shlex.quote(str(pidfile)), shlex.quote(str(marker))
    )
    proc = start_run_tests(repo, queue, command)
    deadline = time.time() + 5
    while time.time() < deadline and not (pidfile.exists() and pidfile.read_text().strip()):
        time.sleep(0.02)
    assert pidfile.exists()
    child_pid = int(pidfile.read_text().strip())
    time.sleep(0.5)
    proc.send_signal(signal.SIGTERM)
    lock = queue / "lock"
    deadline = time.time() + 8
    while time.time() < deadline and lock.exists():
        time.sleep(0.02)
    assert not lock.exists(), "lock was not released after SIGTERM"
    assert not _pid_alive(child_pid), "child still running when lock disappeared"
    assert not marker.exists()
    proc.communicate(timeout=10)
    time.sleep(0.3)
    assert not marker.exists()


# review-fix round 3: a SIGKILLed supervisor leaves its test group running


def test_purge_keeps_lock_while_child_process_group_lives(tmp_path):
    queue = tmp_path / "queue"
    queue.mkdir()
    head = queue / "ticket-{0:020d}-{1}.json".format(1, os.getpid())
    head.write_text(json.dumps({"pid": os.getpid()}), encoding="utf-8")
    child = subprocess.Popen(["sleep", "30"], start_new_session=True)
    try:
        lock = queue / "lock"
        lock.write_text(json.dumps({"pid": 99999999, "child_pgid": child.pid}), encoding="utf-8")
        review_loop._purge_stale_queue_files(queue, head)
        assert lock.exists(), "lock purged while the test process group was alive"
    finally:
        child.kill()
        child.wait(timeout=10)
    review_loop._purge_stale_queue_files(queue, head)
    assert not lock.exists()


def test_run_tests_lock_records_child_pgid(tmp_path):
    repo = serial_repo(tmp_path)
    queue = tmp_path / "queue"
    # The lock gains child_pgid only after the child starts, so wait for it.
    command = (
        'i=0; until grep -q child_pgid "$TLOR_TEST_QUEUE_DIR/lock" || [ $i -ge 100 ]; '
        'do sleep 0.05; i=$((i+1)); done; '
        'cat "$TLOR_TEST_QUEUE_DIR/lock"; echo; ps -o pgid= -p $$'
    )
    proc = run_cli_in(repo, ["run-tests", "--cmd", command], queue_env(queue, "0"))
    result = payload(proc)
    lock_text, pgid_text = result["stdout_tail"].strip().splitlines()
    data = json.loads(lock_text)
    assert isinstance(data["pid"], int)
    assert data["child_pgid"] == int(pgid_text.strip())
    assert sorted(path.name for path in queue.iterdir()) == []
