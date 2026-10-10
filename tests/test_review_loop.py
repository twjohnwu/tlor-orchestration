# -*- coding: utf-8 -*-
"""Tests for the GitHub/GitLab review-loop helper."""
import ast
import json
import os
import subprocess
import sys
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


def test_fetch_review_found_after_two_empty_attempts(tmp_path):
    counter = tmp_path / "fetch-count"
    write_cli(
        tmp_path,
        "gh",
        "import json, os, pathlib, sys\n"
        "if sys.argv[1:3] == ['api', 'user']:\n print('me')\n sys.exit(0)\n"
        "p=pathlib.Path(os.environ['COUNTER'])\n"
        "n=int(p.read_text())+1 if p.exists() else 1\n"
        "p.write_text(str(n))\n"
        "comments=[] if n < 3 else [{'author':{'login':'bot'},'body':'Code review: LGTM',"
        "'createdAt':'2026-01-01T00:00:01Z'}]\n"
        "print(json.dumps({'comments':comments,'reviews':[]}))\n",
    )
    result = payload(
        run_cli(
            ["fetch-review", "--platform", "github", "--since", "2026-01-01T00:00:00Z", "--retries", "4"],
            {"PATH": cli_path(tmp_path), "COUNTER": str(counter)},
        )
    )
    assert result["found"] is True
    assert result["author"] == "bot"
    assert result["attempts"] == 3


def test_fetch_review_not_found_after_retries(tmp_path):
    write_cli(
        tmp_path,
        "gh",
        "import json, sys\n"
        "if sys.argv[1:3] == ['api', 'user']:\n print('me')\n sys.exit(0)\n"
        "print(json.dumps({'comments':[],'reviews':[]}))\n",
    )
    result = payload(
        run_cli(
            ["fetch-review", "--platform", "github", "--since", "2026-01-01T00:00:00Z", "--retries", "2"],
            {"PATH": cli_path(tmp_path)},
        )
    )
    assert result == {"found": False, "body": "", "author": "", "created_at": "", "attempts": 3}


def test_fetch_review_since_is_strict_and_chooses_newest(tmp_path):
    write_cli(
        tmp_path,
        "gh",
        "import json, sys\n"
        "if sys.argv[1:3] == ['api', 'user']:\n print('me')\n sys.exit(0)\n"
        "print(json.dumps({'comments':["
        "{'author':{'login':'bot'},'body':'Review at boundary','createdAt':'2026-01-01T00:00:00Z'},"
        "{'author':{'login':'bot'},'body':'Review newer','createdAt':'2026-01-01T00:00:02+00:00'},"
        "{'author':{'login':'bot'},'body':'Review newest','createdAt':'2026-01-01T00:00:03Z'}"
        "],'reviews':[]}))\n",
    )
    result = payload(
        run_cli(
            ["fetch-review", "--platform", "github", "--since", "2026-01-01T00:00:00Z", "--retries", "0"],
            {"PATH": cli_path(tmp_path)},
        )
    )
    assert result["body"] == "Review newest"
    assert result["created_at"] == "2026-01-01T00:00:03Z"


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
        "parse", "record", "comment", "set-section", "push-time", "elapsed",
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
    write_cli(
        tmp_path,
        "gh",
        "import json, sys\n"
        "a=sys.argv[1:]\n"
        "if a[:2] == ['api','user']:\n print('me')\n sys.exit(0)\n"
        "print(json.dumps({'comments':["
        "{'author':{'login':'bot'},'body':'Review: [High] bug','createdAt':'2026-01-01T00:00:01Z'},"
        "{'author':{'login':'me'},'body':'Review reply: not a bug','createdAt':'2026-01-01T00:00:05Z'}"
        "],'reviews':[]}))\n",
    )
    result = payload(
        run_cli(
            ["fetch-review", "--platform", "github", "--since", "2026-01-01T00:00:00Z", "--retries", "0"],
            {"PATH": cli_path(tmp_path)},
        )
    )
    assert result["author"] == "bot"
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
        "{'author':{'username':'bot'},'body':'Review LGTM','created_at':'2026-01-01T00:00:01Z'}]))\n"
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
        {"author": {"login": "me"}, "body": "review", "createdAt": "2026-01-01T00:00:05Z"},
        {"author": {"login": "bot"}, "body": "review", "createdAt": "2026-01-01T00:00:01Z"},
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
