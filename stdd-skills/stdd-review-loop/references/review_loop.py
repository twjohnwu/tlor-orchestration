#!/usr/bin/env python3
"""Mechanical helpers for an AI code-review loop on GitHub or GitLab.

Run ``review_loop.py --help`` for the thirteen operations.  Every operation emits
one JSON object, making this module suitable for skill prose and shell-free
automation.  The pure helpers near the top are intentionally importable for
unit tests and for callers that only need parsing or text transformations.
"""
import argparse
import datetime
import json
import math
import os
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path


DEFAULT_JOB_PATTERN = r"ai-code-review|ai-review|code-review|review"
DEFAULT_COMMENT_PATTERN = r"(?i)(code review|review|LGTM|critical|high|medium|low|nit)"
BLOCKING_SEVERITIES = {"critical", "high", "medium", "major", "warning", "error"}
NONBLOCKING_SEVERITIES = {"low", "nit", "minor", "info", "suggestion", "trivial"}
KNOWN_SEVERITIES = BLOCKING_SEVERITIES | NONBLOCKING_SEVERITIES
PRIORITY_TAG = re.compile(r"^p(\d+)$", re.I)
SECRET_PATTERN = re.compile(
    r"(github_pat_[A-Za-z0-9_]{20,}|gh[pousr]_[A-Za-z0-9]{20,}|glpat-[A-Za-z0-9_-]{20,})"
)
STDERR_TAIL = 500
GITLAB_PIPELINE_RECHECKS = 6
GITLAB_PIPELINE_RECHECK_SECONDS = 30
QUEUE_UNREADABLE_GRACE_SECONDS = 30

# Process exit codes: 0 is success; 1 is a general command, test, or argparse
# usage error (JsonArgumentParser.error); 3 means fetch-review saw matching
# non-self comments but none was from a bot.
EXIT_ERROR = 1
EXIT_FETCH_REVIEW_NO_BOT = 3


class ReviewLoopError(Exception):
    """An expected failure that should be returned as JSON."""

    def __init__(self, message, stderr=None):
        Exception.__init__(self, message)
        self.stderr = stderr


class JsonArgumentParser(argparse.ArgumentParser):
    """Turn argparse usage errors into the CLI's JSON error contract."""

    def error(self, message):
        raise ReviewLoopError(message)


def platform_for(explicit=None, url=None, remote_url=None):
    """Choose github/gitlab from an override, URL, or resolved remote URL."""
    if explicit:
        return explicit
    candidate = url if url and re.match(r"^https?://", url, re.I) else remote_url
    if candidate is None:
        raise ReviewLoopError("unable to determine platform")
    return "github" if "github.com" in candidate.lower() else "gitlab"


_WORD = r"([A-Za-z][A-Za-z0-9_-]*)"
_MARKDOWN_LINK = re.compile(r"!?\[[^\]\n]*\]\([^)\n]*\)")


def is_blocking(severity):
    """Known non-blocking words and P3+ tags are non-blocking; all else blocks."""
    priority = PRIORITY_TAG.match(severity)
    if priority:
        return int(priority.group(1)) <= 2
    return severity not in NONBLOCKING_SEVERITIES


def _is_known(severity):
    return severity in KNOWN_SEVERITIES or bool(PRIORITY_TAG.match(severity))


def _strip_links(value):
    return _MARKDOWN_LINK.sub("~", value)


# After the severity word a heading may carry only a count, a parenthetical,
# or a colon (``### Critical (2)``, ``### P1: correctness``), so prose
# headings such as ``### Error handling`` or ``## No high-severity issues``
# set no severity.
_HEADING_TAIL = r"(?:\s+(?:issues?|findings?|severity|priority))?\s*(?:\([^)]*\)|\d+)?\s*(?::.*)?$"


def _severity_from_heading(value):
    value = _strip_links(value).replace("*", "").replace("_", "")
    # Drop leading emoji and punctuation, e.g. "🔴 High" or "- High".
    value = re.sub(r"^[^A-Za-z0-9]+", "", value)
    label = re.match(r"severity\s*:\s*" + _WORD + r"\s*(?:\([^)]*\)|\d+)?\s*$", value, re.I)
    if label:
        return label.group(1).lower()
    match = re.match(_WORD + _HEADING_TAIL, value, re.I)
    if match and _is_known(match.group(1).lower()):
        return match.group(1).lower()
    return None


def _inline_severity(value):
    """Return a severity tag at the start of an item, or a ``Severity: X`` label."""
    value = _strip_links(value)
    lead = value
    while True:
        stripped = re.sub(r"^\s*(?:\*\*|__)", "", lead)
        stripped = re.sub(r"^\s*#\d+\b\s*(?:\*\*|__)?\s*[—–:.-]?\s*", "", stripped)
        if stripped == lead:
            break
        lead = stripped
    lead = lead.lstrip()
    bracket = re.match(r"\[\s*" + _WORD + r"\s*\]", lead)
    if bracket and len(bracket.group(1)) > 1:
        # Any bracketed word counts (unknown words block, fail-safe); a
        # one-letter word is a task-list checkbox such as "[x]".
        return bracket.group(1).lower()
    for pattern in (
        _WORD + r"\s*(?:\*\*|__)?\s*:",
        r"\(\s*" + _WORD + r"\s*\)",
        _WORD + r"(?:\*\*|__)(?=\s|$)",
    ):
        match = re.match(pattern, lead)
        if match and _is_known(match.group(1).lower()):
            return match.group(1).lower()
    label = re.search(r"\bSeverity\s*(?:\*\*|__)?\s*:\s*(?:\*\*|__)?\s*" + _WORD, value, re.I)
    return label.group(1).lower() if label else None


_LGTM = re.compile(r"\bLGTM\b|\bLooks\s+good\s+to\s+me\b", re.I)
_LGTM_NEGATED = re.compile(r"(?:\bno|n't|\bnever)\s*[\"'*_`]*\s*$", re.I)
# "not" or "never" anywhere earlier in the same clause negates: "not quite
# LGTM", "not yet LGTM", "not, in its current form, LGTM".
_LGTM_NEGATED_CLAUSE = re.compile(r"\bnot\b|n't\b|\bnever\b", re.I)
_SENTENCE_END = re.compile(r"[.!?](?=\s)|\n")
_LGTM_CONDITIONAL = re.compile(
    r"^[\s\"'*_`.,;:—–-]*(?:once|after|pending|except|but|if|when|until|provided|assuming)\b",
    re.I,
)


def _has_unconditional_lgtm(text):
    for match in _LGTM.finditer(text):
        before = text[max(0, match.start() - 40) : match.start()]
        ends = list(_SENTENCE_END.finditer(before))
        if ends:
            before = before[ends[-1].end() :]
        after = text[match.end() : match.end() + 40]
        if (
            _LGTM_NEGATED.search(before)
            or _LGTM_NEGATED_CLAUSE.search(before)
            or _LGTM_CONDITIONAL.match(after)
        ):
            continue
        return True
    return False


def parse_review(text):
    """Parse review prose into a verdict and normalized findings."""
    findings = []
    context = None
    for line in text.splitlines():
        heading = re.match(r"^\s*#{2,6}\s+(.+?)\s*$", line)
        if heading:
            context = _severity_from_heading(heading.group(1))
            continue

        explicit_number = None
        item = re.match(r"^\s*(?:[-*]\s+|\d+\.\s+)(.+?)\s*$", line)
        numbered = re.match(r"^\s*\*\*#(\d+)\b\s*(.*?)\s*$", line)
        if numbered:
            explicit_number = int(numbered.group(1))
            item_text = numbered.group(2).strip()
            if item_text.endswith("**"):
                item_text = item_text[:-2].rstrip()
        elif item:
            item_text = item.group(1).strip()
        else:
            continue

        severity = _inline_severity(item_text) or context
        if severity is None:
            continue
        path_match = re.search(
            r"`?([A-Za-z0-9_.-]+(?:/[A-Za-z0-9_.-]+)*\.[A-Za-z0-9_-]+):(\d+)`?",
            item_text,
        )
        blocking = is_blocking(severity)
        findings.append(
            {
                "n": explicit_number if explicit_number is not None else len(findings) + 1,
                "severity": severity,
                "blocking": blocking,
                "path": path_match.group(1) if path_match else None,
                "line": int(path_match.group(2)) if path_match else None,
                "text": item_text,
            }
        )

    blocking_count = sum(1 for finding in findings if finding["blocking"])
    changes = bool(
        re.search(r"\b(?:needs\s+changes|request\s+changes|changes\s+requested)\b", text, re.I)
    )
    lgtm = _has_unconditional_lgtm(text)
    if not lgtm:
        lgtm = bool(
            re.search(
                r"(?im)^\s*(?:[-*]\s*)?(?:\*\*)?Approve(?:d)?(?:\*\*)?[.!]?\s*$",
                text,
            )
        )
    if changes or blocking_count:
        verdict = "changes"
    elif lgtm:
        verdict = "lgtm"
    else:
        verdict = "unknown"
    return {"verdict": verdict, "findings": findings, "blocking_count": blocking_count}


def replace_section(text, section_text, heading="## AI Review Fixes"):
    """Replace one level-two section, or append it when it is absent."""
    match = re.search(r"(?m)^" + re.escape(heading) + r"[ \t]*\r?$", text)
    if not match:
        return text + "\n\n" + section_text, False
    next_heading = re.search(r"(?m)^##\s+", text[match.end() :])
    end = match.end() + next_heading.start() if next_heading else len(text)
    replacement = section_text
    if next_heading and replacement and not replacement.endswith("\n"):
        replacement += "\n"
    return text[: match.start()] + replacement + text[end:], True


def _review_section_bounds(text):
    match = re.search(r"(?m)^## Review loop[ \t]*\r?$", text)
    if not match:
        return None
    following = re.search(r"(?m)^##\s+", text[match.end() :])
    end = match.end() + following.start() if following else len(text)
    return match.start(), end


def _section_value(section, key):
    match = re.search(
        r"(?m)^- " + re.escape(key) + r":[ \t]*(.*?)[ \t]*\r?$", section
    )
    return match.group(1) if match else None


def _set_section_line(section, key, value, existed):
    line = "- {0}: {1}".format(key, value)
    if existed:
        return re.sub(
            r"(?m)^- " + re.escape(key) + r":[ \t]*.*?$",
            lambda _match: line,
            section,
            count=1,
        )
    return section + ("" if section.endswith("\n") else "\n") + line + "\n"


def upsert_review_loop_section(
    text,
    minutes=None,
    job=None,
    bot=None,
    max_rounds=None,
    test_command=None,
    lint_command=None,
    tests=None,
):
    """Update Review loop values while preserving every unrelated byte.

    Returns ``(text, minutes_written, job_written, bot_written, minutes, job,
    bot)`` where the last three are the values in effect afterwards.  The
    additional settings are updated without changing this legacy return shape.
    """
    bounds = _review_section_bounds(text)
    section = text[bounds[0] : bounds[1]] if bounds else ""
    old_minutes_text = _section_value(section, "ci-wait-minutes")
    old_job = _section_value(section, "review-job-name")
    old_bot = _section_value(section, "review-bot")
    extra_values = (
        ("max-rounds", max_rounds),
        ("test-command", test_command),
        ("lint-command", lint_command),
        ("tests", tests),
    )
    try:
        old_minutes = int(old_minutes_text) if old_minutes_text is not None else None
    except ValueError:
        old_minutes = None

    new_minutes = int(math.ceil(minutes)) if minutes is not None else None
    minutes_written = False
    if new_minutes is not None:
        if old_minutes is None or old_minutes == 0:
            minutes_written = old_minutes != new_minutes
        else:
            minutes_written = abs(new_minutes - old_minutes) / float(abs(old_minutes)) > 0.20
    job_written = job is not None and job != old_job
    bot_written = bot is not None and bot != old_bot
    extra_writes = [
        (key, value, _section_value(section, key))
        for key, value in extra_values
        if value is not None and str(value) != _section_value(section, key)
    ]
    current_minutes = new_minutes if minutes_written else old_minutes
    current_job = job if job_written else old_job
    current_bot = bot if bot_written else old_bot

    if not minutes_written and not job_written and not bot_written and not extra_writes:
        return text, False, False, False, old_minutes, old_job, old_bot

    if not bounds:
        separator = "" if not text else ("" if text.endswith("\n\n") else "\n" if text.endswith("\n") else "\n\n")
        additions = ["## Review loop"]
        if minutes_written:
            additions.append("- ci-wait-minutes: {0}".format(new_minutes))
        if job_written:
            additions.append("- review-job-name: {0}".format(job))
        if bot_written:
            additions.append("- review-bot: {0}".format(bot))
        for key, value, _old_value in extra_writes:
            additions.append("- {0}: {1}".format(key, value))
        updated = text + separator + "\n".join(additions) + "\n"
    else:
        updated_section = section
        if minutes_written:
            updated_section = _set_section_line(
                updated_section, "ci-wait-minutes", new_minutes, old_minutes_text is not None
            )
        if job_written:
            updated_section = _set_section_line(
                updated_section, "review-job-name", job, old_job is not None
            )
        if bot_written:
            updated_section = _set_section_line(
                updated_section, "review-bot", bot, old_bot is not None
            )
        for key, value, old_value in extra_writes:
            updated_section = _set_section_line(
                updated_section, key, value, old_value is not None
            )
        updated = text[: bounds[0]] + updated_section + text[bounds[1] :]
    return (
        updated,
        minutes_written,
        job_written,
        bot_written,
        current_minutes,
        current_job,
        current_bot,
    )


def parse_utc_timestamp(value):
    """Parse an ISO-8601 timestamp into an aware UTC datetime on Python 3.7."""
    normalized = value.strip()
    if normalized.endswith("Z"):
        normalized = normalized[:-1] + "+00:00"
    parsed = datetime.datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=datetime.timezone.utc)
    return parsed.astimezone(datetime.timezone.utc)


def pick_latest_comment(
    comments, since, pattern=DEFAULT_COMMENT_PATTERN, author=None, exclude=(), bot_only=False
):
    """Return the newest normalized comment strictly newer than ``since``.

    Comments by any login in ``exclude`` (the authenticated user) never count.
    """
    candidates = _matching_comments(comments, since, pattern, author, exclude)
    if bot_only:
        candidates = [candidate for candidate in candidates if candidate[4]]
    if not candidates:
        return None
    newest = max(candidates, key=lambda value: value[0])
    return {"body": newest[1], "author": newest[2], "created_at": newest[3]}


def _normalize_login(login):
    """Drop a trailing ``[bot]`` so ``x`` and ``x[bot]`` compare equal."""
    if isinstance(login, str) and login.endswith("[bot]"):
        return login[: -len("[bot]")]
    return login


def _comment_author(comment):
    author = comment.get("author")
    if not isinstance(author, dict):
        author = comment.get("user")
    if isinstance(author, dict):
        login = author.get("login") or author.get("username")
        is_bot = bool(
            (isinstance(login, str) and login.endswith("[bot]"))
            or author.get("type") == "Bot"
            or author.get("bot") is True
        )
        return login, is_bot
    return author, isinstance(author, str) and author.endswith("[bot]")


def _matching_comments(comments, since, pattern, author, exclude):
    since_time = parse_utc_timestamp(since) if isinstance(since, str) else since
    matcher = re.compile(pattern)
    excluded = set(_normalize_login(value) for value in exclude)
    wanted = _normalize_login(author)
    candidates = []
    for comment in comments:
        if comment.get("system"):
            continue
        login, is_bot = _comment_author(comment)
        created = comment.get("created_at") or comment.get("submitted_at")
        body = comment.get("body") or ""
        if (
            not created
            or (login is not None and _normalize_login(login) in excluded)
            or (author is not None and _normalize_login(login) != wanted)
            or not matcher.search(body)
        ):
            continue
        created_time = parse_utc_timestamp(created)
        if created_time > since_time:
            candidates.append((created_time, body, login or "", created, is_bot))
    return candidates


def _candidate_authors(comments, since, pattern, exclude):
    candidates = _matching_comments(comments, since, pattern, None, exclude)
    candidates.sort(key=lambda value: value[0], reverse=True)
    authors = []
    for candidate in candidates:
        login = _normalize_login(candidate[2])
        if login and login not in authors:
            authors.append(login)
    return authors


def _check_category(check):
    value = str(
        check.get("bucket")
        or check.get("status")
        or check.get("state")
        or check.get("conclusion")
        or ""
    ).lower()
    if value in (
        "pending", "running", "created", "queued", "in_progress",
        "waiting_for_resource", "preparing", "scheduled", "canceling",
    ):
        return "pending"
    if value in ("fail", "failed", "failure", "timed_out", "action_required"):
        return "failed"
    if value in ("cancel", "cancelled", "canceled"):
        return "canceled"
    if value in ("manual", "skipped"):
        return "success"
    return "success"


def _top_level_alternatives(pattern):
    """Split a regex on its top-level ``|``, keeping priority order."""
    parts = []
    depth = 0
    in_class = False
    escaped = False
    start = 0
    for index, char in enumerate(pattern):
        if escaped:
            escaped = False
        elif char == "\\":
            escaped = True
        elif in_class:
            in_class = char != "]"
        elif char == "[":
            in_class = True
        elif char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
        elif char == "|" and depth == 0:
            parts.append(pattern[start:index])
            start = index + 1
    parts.append(pattern[start:])
    return [part for part in parts if part] or [pattern]


def _counted_category(check, review):
    """Category for the summary; a non-review GitLab job allowed to fail
    (``allow_failure: true``) never counts as failed or canceled."""
    category = _check_category(check)
    if check is not review and check.get("allow_failure") is True and category in (
        "failed", "canceled",
    ):
        return "success"
    return category


def summarize_checks(checks, job=None, job_pattern=DEFAULT_JOB_PATTERN):
    """Summarize normalized GitHub checks or GitLab jobs."""
    if not checks:
        return {
            "status": "none",
            "review_job": None,
            "review_job_status": None,
            "failed_jobs": [],
            "canceled_jobs": [],
        }
    review = None
    if job is not None:
        for check in checks:
            if (check.get("name") or "") == job:
                review = check
                break
    else:
        # Earlier alternatives in the pattern win over list order, so a
        # generic "review" cannot shadow "ai-code-review".
        for alternative in _top_level_alternatives(job_pattern):
            matcher = re.compile(alternative, re.I)
            review = next(
                (check for check in checks if matcher.search(check.get("name") or "")),
                None,
            )
            if review is not None:
                break
    failed_jobs = [
        check.get("name") or ""
        for check in checks
        if check is not review and _counted_category(check, review) == "failed"
    ]
    canceled_jobs = [
        check.get("name") or ""
        for check in checks
        if check is not review and _counted_category(check, review) == "canceled"
    ]
    categories = [_counted_category(check, review) for check in checks]
    if "pending" in categories:
        status = "running"
    elif review is not None and _check_category(review) == "failed":
        status = "failed"
    elif review is not None and _check_category(review) == "canceled":
        status = "canceled"
    elif "failed" in categories:
        status = "failed"
    elif "canceled" in categories:
        status = "canceled"
    else:
        status = "success"
    review_status = None
    if review is not None:
        review_status = str(review.get("status") or review.get("state") or review.get("bucket") or "")
    return {
        "status": status,
        "review_job": (review.get("name") or "") if review is not None else None,
        "review_job_status": review_status if review is not None else None,
        "failed_jobs": failed_jobs,
        "canceled_jobs": canceled_jobs,
    }


def scaled_sleep(seconds):
    """Sleep through the single test-scalable timing seam."""
    try:
        scale = float(os.environ.get("REVIEW_LOOP_SLEEP_SCALE", "1.0"))
    except ValueError:
        raise ReviewLoopError("REVIEW_LOOP_SLEEP_SCALE must be a number")
    if scale < 0:
        raise ReviewLoopError("REVIEW_LOOP_SLEEP_SCALE must not be negative")
    time.sleep(seconds * scale)


def redact_text(text):
    """Mask GitHub and GitLab access tokens in arbitrary output."""
    return SECRET_PATTERN.sub("[REDACTED]", text or "")


def redact_stderr(text):
    """Mask CLI tokens, then keep only the tail of a CLI's stderr."""
    return redact_text(text)[-STDERR_TAIL:]


def _run(args, allow_nonzero_json=False, discard=False):
    try:
        proc = subprocess.run(
            args,
            stdout=subprocess.DEVNULL if discard else subprocess.PIPE,
            stderr=subprocess.DEVNULL if discard else subprocess.PIPE,
            universal_newlines=True,
        )
    except FileNotFoundError:
        raise ReviewLoopError("{0} is not installed".format(args[0]))
    except OSError:
        raise ReviewLoopError("unable to run {0}".format(args[0]))
    if proc.returncode != 0 and not allow_nonzero_json:
        raise ReviewLoopError(
            "{0} command failed (exit {1})".format(args[0], proc.returncode),
            stderr=redact_stderr(proc.stderr),
        )
    return proc


def _json_command(args, allow_nonzero=False):
    proc = _run(args, allow_nonzero_json=allow_nonzero)
    try:
        return json.loads(proc.stdout)
    except (TypeError, ValueError):
        raise ReviewLoopError("{0} returned invalid JSON".format(args[0]))


def _remote_url():
    proc = _run(["git", "remote", "get-url", "origin"])
    return proc.stdout.strip()


def _branch_remote_url(branch):
    proc = _run(
        ["git", "config", "branch.{0}.remote".format(branch)], allow_nonzero_json=True
    )
    remote = proc.stdout.strip() if proc.returncode == 0 else ""
    if not remote or remote == ".":
        remote = "origin"
    return _run(["git", "remote", "get-url", remote]).stdout.strip()


def _repo_root():
    proc = _run(["git", "rev-parse", "--show-toplevel"])
    return proc.stdout.strip()


def _selected_platform(args):
    if args.platform:
        return args.platform
    if getattr(args, "url", None) and re.match(r"^https?://", args.url, re.I):
        return platform_for(url=args.url)
    if getattr(args, "branch", None):
        return platform_for(remote_url=_branch_remote_url(args.branch))
    return platform_for(remote_url=_remote_url())


def _ref_args(ref):
    return [str(ref)] if ref else []


def _view(platform, ref):
    if platform == "github":
        data = _json_command(
            ["gh", "pr", "view"]
            + _ref_args(ref)
            + ["--json", "number,url,headRefOid,headRefName,body"]
        )
        return {
            "platform": "github",
            "number": data.get("number"),
            "url": data.get("url"),
            "head_sha": data.get("headRefOid"),
            "branch": data.get("headRefName"),
            "description": data.get("body") or "",
        }
    data = _json_command(["glab", "mr", "view"] + _ref_args(ref) + ["-F", "json"])
    sha = data.get("sha")
    if sha is None and isinstance(data.get("diff_refs"), dict):
        sha = data["diff_refs"].get("head_sha")
    return {
        "platform": "gitlab",
        "number": data.get("iid"),
        "url": data.get("web_url"),
        "head_sha": sha,
        "branch": data.get("source_branch"),
        "description": data.get("description") or "",
        "_raw": data,
    }


def _glab_api_json(method, endpoint, fields):
    """Send a JSON body to glab from a temp file so long text never rides argv."""
    temp_name = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", delete=False) as handle:
            json.dump(fields, handle)
            temp_name = handle.name
        _run(
            [
                "glab",
                "api",
                "--method",
                method,
                endpoint,
                "--input",
                temp_name,
                "-H",
                "Content-Type: application/json",
            ]
        )
    finally:
        if temp_name is not None:
            try:
                os.unlink(temp_name)
            except OSError:
                pass


def _write_description(platform, ref, number, text, body_file=None):
    if platform == "github":
        if body_file is not None:
            _run(["gh", "pr", "edit"] + _ref_args(ref) + ["--body-file", str(body_file)])
            return
        temp_name = None
        try:
            with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", delete=False) as handle:
                handle.write(text)
                temp_name = handle.name
            _run(["gh", "pr", "edit"] + _ref_args(ref) + ["--body-file", temp_name])
        finally:
            if temp_name is not None:
                try:
                    os.unlink(temp_name)
                except OSError:
                    pass
        return
    if number is None:
        raise ReviewLoopError("merge request JSON is missing iid")
    _glab_api_json(
        "PUT", "projects/:id/merge_requests/{0}".format(number), {"description": text}
    )


def _checks(platform, ref):
    if platform == "github":
        proc = _run(
            ["gh", "pr", "checks"] + _ref_args(ref) + ["--json", "name,state,bucket,link"],
            allow_nonzero_json=True,
        )
        if not (proc.stdout or "").strip():
            # gh prints nothing when the PR has no checks, whatever its exit code.
            return []
        try:
            data = json.loads(proc.stdout)
        except (TypeError, ValueError):
            if proc.returncode != 0:
                # gh exits non-zero with no JSON when the PR has no checks.
                return []
            raise ReviewLoopError("gh returned invalid JSON")
        if not isinstance(data, list):
            raise ReviewLoopError("gh returned unexpected checks JSON")
        return data
    mr = _json_command(["glab", "mr", "view"] + _ref_args(ref) + ["-F", "json"])
    pipeline = mr.get("head_pipeline") or mr.get("pipeline") or {}
    pipeline_id = pipeline.get("id") if isinstance(pipeline, dict) else None
    if pipeline_id is None:
        return []
    data = _json_command(
        ["glab", "api", "projects/:id/pipelines/{0}/jobs?per_page=100".format(pipeline_id)]
    )
    if not isinstance(data, list):
        raise ReviewLoopError("glab returned unexpected jobs JSON")
    return data


def _paginated_json(args):
    """Run a ``gh api --paginate`` call and join its concatenated JSON pages."""
    text = _run(args).stdout
    decoder = json.JSONDecoder()
    items = []
    position = 0
    while True:
        while position < len(text) and text[position].isspace():
            position += 1
        if position >= len(text):
            return items
        try:
            page, position = decoder.raw_decode(text, position)
        except ValueError:
            raise ReviewLoopError("{0} returned invalid JSON".format(args[0]))
        if not isinstance(page, list):
            raise ReviewLoopError("{0} returned unexpected JSON".format(args[0]))
        items.extend(page)


def _github_comments(ref, inline=False):
    """Issue comments and reviews via REST, whose users carry ``type`` (Bot/User)."""
    number = _view("github", ref).get("number")
    if number is None:
        raise ReviewLoopError("pull request JSON is missing number")
    endpoints = ["issues/{0}/comments", "pulls/{0}/reviews"]
    if inline:
        endpoints.append("pulls/{0}/comments")
    comments = []
    for endpoint in endpoints:
        comments.extend(
            _paginated_json(
                ["gh", "api", "--paginate", "repos/{owner}/{repo}/" + endpoint.format(number)]
            )
        )
    return comments


def _comments(platform, ref):
    if platform == "github":
        return _github_comments(ref)
    mr = _view("gitlab", ref)
    if mr["number"] is None:
        raise ReviewLoopError("merge request JSON is missing iid")
    data = _json_command(
        [
            "glab",
            "api",
            "projects/:id/merge_requests/{0}/notes?sort=desc&order_by=created_at&per_page=100".format(
                mr["number"]
            ),
        ]
    )
    if not isinstance(data, list):
        raise ReviewLoopError("glab returned unexpected notes JSON")
    return data


def _comments_with_inline(platform, ref):
    if platform != "github":
        return _comments(platform, ref)
    return _github_comments(ref, inline=True)


def command_preflight(args):
    platform = _selected_platform(args)
    cli = "gh" if platform == "github" else "glab"
    installed = shutil.which(cli) is not None
    logged_in = False
    if installed:
        logged_in = _run([cli, "auth", "status"], allow_nonzero_json=True, discard=True).returncode == 0
    if not installed:
        hint = "brew install {0}".format(cli)
    elif not logged_in:
        hint = "! {0} auth login".format(cli)
    else:
        hint = ""
    return {
        "platform": platform,
        "branch": getattr(args, "branch", None),
        "cli": cli,
        "installed": installed,
        "logged_in": logged_in,
        "hint": hint,
    }


def command_detect(args):
    result = _view(_selected_platform(args), args.pr)
    result.pop("_raw", None)
    return result


def command_wait(args):
    platform = _selected_platform(args)
    waited = 0.0
    extensions = 0
    while True:
        scaled_sleep(args.minutes * 60.0)
        waited += args.minutes
        checks = _checks(platform, args.pr)
        summary = summarize_checks(checks, args.job, args.job_pattern)
        if summary["status"] != "running" or extensions >= args.max_extensions:
            summary["waited_minutes"] = waited
            summary["extensions"] = extensions
            return summary
        extensions += 1


def command_ensure_description(args):
    platform = _selected_platform(args)
    viewed = _view(platform, args.pr)
    if viewed["description"].strip():
        return {"written": False}
    template_text = Path(args.template).read_text(encoding="utf-8")
    _write_description(
        platform, args.pr, viewed["number"], template_text, body_file=args.template
    )
    return {"written": True}


def _self_login(platform):
    """Login of the authenticated CLI user, whose comments are never reviews."""
    if platform == "github":
        login = _run(["gh", "api", "user", "--jq", ".login"]).stdout.strip()
    else:
        data = _json_command(["glab", "api", "user"])
        login = data.get("username") if isinstance(data, dict) else None
    if not login:
        raise ReviewLoopError("unable to determine the authenticated user")
    return login


def command_fetch_review(args):
    platform = _selected_platform(args)
    self_login = _self_login(platform)
    candidate_authors = []
    for attempt in range(1, args.retries + 2):
        comments = _comments(platform, args.pr)
        found = pick_latest_comment(
            comments,
            args.since,
            args.pattern,
            args.author,
            exclude=(self_login,),
            bot_only=args.author is None,
        )
        if found is not None:
            result = {"found": True}
            result.update(found)
            result["attempts"] = attempt
            return result
        if args.author is None:
            candidate_authors = _candidate_authors(
                comments, args.since, args.pattern, (self_login,)
            )
        if attempt <= args.retries:
            scaled_sleep(args.interval)
    if args.author is None and candidate_authors:
        return {
            "found": False,
            "candidate_authors": candidate_authors,
            "attempts": args.retries + 1,
            "_exit_code": EXIT_FETCH_REVIEW_NO_BOT,
        }
    return {"found": False, "body": "", "author": "", "created_at": "", "attempts": args.retries + 1}


def command_fetch_comments(args):
    platform = _selected_platform(args)
    excluded = set(_normalize_login(value) for value in (args.exclude_author or ()))
    excluded.add(_normalize_login(_self_login(platform)))
    since = parse_utc_timestamp(args.since)
    checked_at = _utc_iso(datetime.datetime.now(datetime.timezone.utc))
    results = []
    for comment in _comments_with_inline(platform, args.pr):
        if comment.get("system"):
            continue
        login, _is_bot = _comment_author(comment)
        created = comment.get("created_at") or comment.get("submitted_at")
        if (
            not created
            or _normalize_login(login) in excluded
            or not (comment.get("body") or "").strip()
        ):
            continue
        created_time = parse_utc_timestamp(created)
        if created_time <= since:
            continue
        item = {
            "author": login or "",
            "created_at": created,
            "body": comment.get("body") or "",
        }
        position = comment.get("position")
        if not isinstance(position, dict):
            position = {}
        path = comment.get("path") or position.get("new_path")
        line = comment.get("line")
        if line is None:
            line = comment.get("original_line")
        if line is None:
            line = position.get("new_line")
        if path is not None:
            item["path"] = path
        if line is not None:
            item["line"] = line
        results.append((created_time, item))
    results.sort(key=lambda value: value[0])
    return {"comments": [item for _created, item in results], "checked_at": checked_at}


def command_parse(args):
    return parse_review(sys.stdin.read())


def _record_values(text):
    bounds = _review_section_bounds(text)
    if not bounds:
        return None, None, None
    section = text[bounds[0] : bounds[1]]
    minutes_text = _section_value(section, "ci-wait-minutes")
    try:
        minutes = int(minutes_text) if minutes_text is not None else None
    except ValueError:
        minutes = None
    return (
        minutes,
        _section_value(section, "review-job-name"),
        _section_value(section, "review-bot"),
    )


def _new_record_values(text, local_text=""):
    bounds = _review_section_bounds(text)
    section = text[bounds[0] : bounds[1]] if bounds else ""
    max_rounds_text = _section_value(section, "max-rounds")
    if max_rounds_text is None:
        max_rounds = 10
    else:
        try:
            max_rounds = int(max_rounds_text)
        except ValueError:
            raise ReviewLoopError("max-rounds must be a positive integer")
        if max_rounds < 1:
            raise ReviewLoopError("max-rounds must be a positive integer")

    local_bounds = _review_section_bounds(local_text)
    local_section = local_text[local_bounds[0] : local_bounds[1]] if local_bounds else ""
    tests = _section_value(local_section, "tests") or "never"
    if tests not in ("never", "serial"):
        raise ReviewLoopError("tests must be never or serial")
    return {
        "max_rounds": max_rounds,
        "test_command": _section_value(section, "test-command"),
        "lint_command": _section_value(section, "lint-command"),
        "tests": tests,
    }


def _settings_result(path, text, local_text):
    minutes, job, bot = _record_values(text)
    result = {
        "path": str(path),
        "ci_wait_minutes": minutes,
        "review_job_name": job,
        "review_bot": bot,
    }
    result.update(_new_record_values(text, local_text))
    return result


def _read_text_exact(path):
    with path.open("r", encoding="utf-8", newline="") as handle:
        return handle.read()


def _write_text_exact(path, text):
    with path.open("w", encoding="utf-8", newline="") as handle:
        handle.write(text)


def command_record(args):
    agents_path = Path(args.agents) if args.agents else Path(_repo_root()) / "AGENTS.md"
    local_path = agents_path.parent / "AGENTS.local.md"
    text = _read_text_exact(agents_path) if agents_path.exists() else ""
    local_text = _read_text_exact(local_path) if local_path.exists() else ""
    if args.max_rounds is not None and args.max_rounds < 1:
        raise ReviewLoopError("max-rounds must be a positive integer")
    if args.show:
        result = _settings_result(agents_path, text, local_text)
        result.update({
            "minutes_written": False,
            "job_written": False,
            "bot_written": False,
            "max_rounds_written": False,
            "test_command_written": False,
            "lint_command_written": False,
            "tests_written": False,
        })
        return result

    if args.local:
        if any(
            value is not None
            for value in (
                args.minutes,
                args.job,
                args.bot,
                args.max_rounds,
                args.test_command,
                args.lint_command,
            )
        ):
            raise ReviewLoopError("--local only accepts --tests")
        if args.tests is None:
            raise ReviewLoopError("--local requires --tests")
        old_tests = _section_value(
            local_text[_review_section_bounds(local_text)[0] : _review_section_bounds(local_text)[1]]
            if _review_section_bounds(local_text)
            else "",
            "tests",
        )
        ignored = False
        try:
            ignored = subprocess.run(
                ["git", "check-ignore", "-q", "AGENTS.local.md"],
                cwd=str(agents_path.parent),
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            ).returncode == 0
        except OSError:
            ignored = False
        updated = upsert_review_loop_section(local_text, tests=args.tests)[0]
        if updated != local_text or not local_path.exists():
            _write_text_exact(local_path, updated)
        result = _settings_result(local_path, text, updated)
        result.update({
            "minutes_written": False,
            "job_written": False,
            "bot_written": False,
            "max_rounds_written": False,
            "test_command_written": False,
            "lint_command_written": False,
            "tests_written": args.tests is not None and args.tests != old_tests,
        })
        if not ignored:
            result["warning"] = "AGENTS.local.md is not gitignored; add it to .gitignore"
        return result

    if args.tests is not None:
        raise ReviewLoopError("--tests requires --local")
    old_bounds = _review_section_bounds(text)
    old_section = text[old_bounds[0] : old_bounds[1]] if old_bounds else ""
    old_raw = {
        key: _section_value(old_section, key)
        for key in ("max-rounds", "test-command", "lint-command")
    }
    (
        updated,
        minutes_written,
        job_written,
        bot_written,
        minutes,
        job,
        bot,
    ) = upsert_review_loop_section(
        text,
        args.minutes,
        args.job,
        args.bot,
        args.max_rounds,
        args.test_command,
        args.lint_command,
    )
    if updated != text or not agents_path.exists():
        _write_text_exact(agents_path, updated)
    result = _settings_result(agents_path, updated, local_text)
    result.update({
        "minutes_written": minutes_written,
        "job_written": job_written,
        "bot_written": bot_written,
        "max_rounds_written": args.max_rounds is not None
        and str(args.max_rounds) != old_raw.get("max-rounds"),
        "test_command_written": args.test_command is not None
        and args.test_command != old_raw.get("test-command"),
        "lint_command_written": args.lint_command is not None
        and args.lint_command != old_raw.get("lint-command"),
        "tests_written": False,
    })
    return result


def _pid_alive(pid):
    if not isinstance(pid, int) or pid < 1:
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return False
    return True


def _pgid_alive(pgid):
    if not isinstance(pgid, int) or isinstance(pgid, bool) or pgid < 1:
        return False
    try:
        os.killpg(pgid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return False
    return True


def _queue_file_child_pgid(path):
    """``child_pgid`` recorded in a lock once its test command started; None
    when absent or unreadable."""
    try:
        data = json.loads(path.read_text(encoding="utf-8").strip())
    except (OSError, TypeError, ValueError):
        return None
    pgid = data.get("child_pgid") if isinstance(data, dict) else None
    if isinstance(pgid, bool) or not isinstance(pgid, int):
        return None
    return pgid


def _queue_file_pid(path):
    """Pid recorded in a ticket, lock, or temp file (``{"pid": N}``, or a bare
    number from older locks); None when unreadable or empty."""
    try:
        data = json.loads(path.read_text(encoding="utf-8").strip())
        if isinstance(data, dict):
            data = data.get("pid")
        if isinstance(data, bool) or not isinstance(data, int):
            return None
        return data
    except (OSError, TypeError, ValueError):
        return None


def _purge_stale_queue_files(queue_dir, own_ticket=None):
    """Drop queue files left by dead processes.  A file whose pid is alive is
    never purged, however old; a file with no readable pid is purged only
    after QUEUE_UNREADABLE_GRACE_SECONDS.  Only the waiter whose ticket
    (``own_ticket``) is the queue head may purge ``lock``: two purgers could
    otherwise both read a dead lock while a third links a live one, and the
    unlink would delete it."""
    now = time.time()
    paths = list(queue_dir.glob("ticket-*.json"))
    paths.extend(queue_dir.glob(".tmp-*"))
    for path in paths:
        _purge_if_stale(path, now)
    tickets = sorted(queue_dir.glob("ticket-*.json"), key=lambda path: path.name)
    if own_ticket is not None and tickets and tickets[0] == own_ticket:
        _purge_if_stale(queue_dir / "lock", now)


def _purge_if_stale(path, now):
    if not path.exists():
        return
    pid = _queue_file_pid(path)
    if pid is None:
        try:
            stale = now - path.stat().st_mtime > QUEUE_UNREADABLE_GRACE_SECONDS
        except OSError:
            return
    else:
        # A SIGKILLed supervisor leaves its test command running in its own
        # process group; the lock stays held until that group is gone too.
        stale = not _pid_alive(pid) and not _pgid_alive(_queue_file_child_pgid(path))
    if stale:
        try:
            path.unlink()
        except FileNotFoundError:
            pass


def _write_exclusive(path, text):
    """Create ``path`` holding ``text``, or return False if it exists.  The
    content goes to a temp file first and is hard-linked into place, so no
    other process ever sees ``path`` empty."""
    temp = path.parent / ".tmp-{0}-{1}".format(os.getpid(), time.time_ns())
    descriptor = os.open(str(temp), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    try:
        try:
            os.write(descriptor, text.encode("utf-8"))
        finally:
            os.close(descriptor)
        try:
            os.link(str(temp), str(path))
        except FileExistsError:
            return False
        return True
    finally:
        try:
            temp.unlink()
        except FileNotFoundError:
            pass


def _replace_atomic(path, text):
    """Rewrite ``path`` with ``text`` through a temp file in the same
    directory and ``os.replace``, so no reader ever sees it partial."""
    temp = path.parent / ".tmp-{0}-{1}".format(os.getpid(), time.time_ns())
    descriptor = os.open(str(temp), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    try:
        try:
            os.write(descriptor, text.encode("utf-8"))
        finally:
            os.close(descriptor)
        os.replace(str(temp), str(path))
    finally:
        try:
            temp.unlink()
        except FileNotFoundError:
            pass


def _remove_owned_lock(path, pid):
    if _queue_file_pid(path) != pid:
        return
    try:
        path.unlink()
    except FileNotFoundError:
        pass


def _repo_root_or_cwd():
    try:
        proc = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            universal_newlines=True,
        )
    except OSError:
        return Path.cwd()
    root = proc.stdout.strip()
    return Path(root) if proc.returncode == 0 and root else Path.cwd()


def command_run_tests(args):
    repo_cwd = Path.cwd()
    settings_root = _repo_root_or_cwd()
    agents_path = settings_root / "AGENTS.md"
    local_path = settings_root / "AGENTS.local.md"
    agents_text = _read_text_exact(agents_path) if agents_path.exists() else ""
    local_text = _read_text_exact(local_path) if local_path.exists() else ""
    settings = _new_record_values(agents_text, local_text)
    if settings["tests"] == "never":
        raise ReviewLoopError("tests policy is never")
    command = args.cmd or settings["test_command"]
    if not command:
        raise ReviewLoopError("no test command configured; use --cmd or record --test-command")
    if not command.strip():
        raise ReviewLoopError("test command is empty")
    if args.timeout < 0:
        raise ReviewLoopError("timeout must not be negative")

    queue_dir = Path(
        os.environ.get("TLOR_TEST_QUEUE_DIR", str(Path.home() / ".claude" / "tlor" / "test-queue"))
    ).expanduser()
    queue_dir.mkdir(parents=True, exist_ok=True)
    pid = os.getpid()
    created = time.time()
    ticket = queue_dir / "ticket-{0:020d}-{1}.json".format(time.time_ns(), pid)
    ticket_data = {
        "pid": pid,
        "cwd": str(repo_cwd),
        "command": command,
        "created": created,
    }
    if not _write_exclusive(ticket, json.dumps(ticket_data, separators=(",", ":"))):
        raise ReviewLoopError("unable to create a unique test queue ticket")

    wait_started = time.monotonic()
    lock = queue_dir / "lock"
    acquired = False
    try:
        while True:
            _purge_stale_queue_files(queue_dir, ticket)
            tickets = sorted(queue_dir.glob("ticket-*.json"), key=lambda path: path.name)
            if tickets and tickets[0] == ticket:
                acquired = _write_exclusive(lock, json.dumps({"pid": pid}))
                if acquired:
                    break
            if time.monotonic() - wait_started >= args.timeout:
                return {"status": "timeout"}
            scaled_sleep(0.5)

        waited = time.monotonic() - wait_started
        run_started = time.monotonic()
        # A shell command line (``cd x && pytest``, ``CI=1 make test``), run
        # by /bin/sh with an explicit argv rather than shell=True. The child
        # gets its own session so SIGTERM/SIGHUP/Ctrl-C can kill the whole
        # process group and the lock is only released once it is gone.
        def terminate(signum, frame):
            raise SystemExit(128 + signum)

        previous = {}
        child = None
        try:
            for sig in (signal.SIGTERM, signal.SIGHUP):
                previous[sig] = signal.signal(sig, terminate)
            try:
                child = subprocess.Popen(
                    ["/bin/sh", "-c", command],
                    cwd=str(repo_cwd),
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    universal_newlines=True,
                    start_new_session=True,
                )
            except OSError:
                raise ReviewLoopError("unable to run /bin/sh")
            try:
                # The child leads its own session, so its pid is its pgid.
                _replace_atomic(lock, json.dumps({"pid": pid, "child_pgid": child.pid}))
                stdout, stderr = child.communicate()
            except BaseException:
                _kill_process_group(child)
                raise
        finally:
            for sig, handler in previous.items():
                signal.signal(sig, handler)
        proc = subprocess.CompletedProcess(child.args, child.returncode, stdout, stderr)
        duration = time.monotonic() - run_started
        return {
            "status": "ok" if proc.returncode == 0 else "failed",
            "exit_code": proc.returncode,
            "waited_seconds": waited,
            "duration_seconds": duration,
            "stdout_tail": redact_text(proc.stdout)[-4000:],
            "stderr_tail": redact_text(proc.stderr)[-4000:],
        }
    finally:
        if acquired:
            _remove_owned_lock(lock, pid)
        try:
            ticket.unlink()
        except FileNotFoundError:
            pass


def _kill_process_group(child):
    """SIGTERM the child's process group, SIGKILL after 5 s, and reap it."""
    for sig, wait in ((signal.SIGTERM, 5), (signal.SIGKILL, None)):
        try:
            os.killpg(child.pid, sig)
        except (ProcessLookupError, PermissionError):
            pass
        try:
            child.wait(timeout=wait)
            return
        except subprocess.TimeoutExpired:
            continue


def _log_tail(text, lines):
    if lines < 1:
        raise ReviewLoopError("lines must be a positive integer")
    return "\n".join(redact_text(text).splitlines()[-lines:])


def _github_actions_job_ids(check, job_name):
    link = re.match(
        r"^https://[^/]+/[^/]+/[^/]+/actions/runs/(\d+)/jobs?/(\d+)(?:[/?#]|$)",
        str(check.get("link") or ""),
    )
    if link is None:
        raise ReviewLoopError("not a GitHub Actions job: {0}".format(job_name))
    return link.group(1), link.group(2)


def command_rerun_review(args):
    platform = _selected_platform(args)
    checks = _checks(platform, args.pr)
    summary = summarize_checks(checks, args.job, args.job_pattern)
    job_name = summary["review_job"]
    if job_name is None:
        raise ReviewLoopError("review job not found")
    match = next((check for check in checks if (check.get("name") or "") == job_name), None)
    if match is None:
        raise ReviewLoopError("review job not found: {0}".format(job_name))
    if platform == "github":
        run_id, job_id = _github_actions_job_ids(match, job_name)
        command = ["gh", "run", "rerun", run_id, "--job", job_id]
    else:
        job_id = match.get("id")
        if job_id is None:
            raise ReviewLoopError("review job is missing id: {0}".format(job_name))
        command = ["glab", "api", "-X", "POST", "projects/:id/jobs/{0}/retry".format(job_id)]
    since = datetime.datetime.now(datetime.timezone.utc).isoformat().replace("+00:00", "Z")
    _run(command)
    return {"since": since, "job": job_name}


def command_job_log(args):
    platform = _selected_platform(args)
    if platform == "github":
        proc = _run(
            ["gh", "pr", "checks"] + _ref_args(args.pr) + ["--json", "name,link,state,bucket"],
            allow_nonzero_json=True,
        )
        try:
            checks = json.loads(proc.stdout)
        except (TypeError, ValueError):
            raise ReviewLoopError("gh returned invalid JSON")
        if not isinstance(checks, list):
            raise ReviewLoopError("gh returned unexpected checks JSON")
        match = next(
            (
                check
                for check in checks
                if check.get("name") == args.job and _check_category(check) == "failed"
            ),
            None,
        )
        if match is None:
            raise ReviewLoopError("failed job not found: {0}".format(args.job))
        run_id, job_id = _github_actions_job_ids(match, args.job)
        view = ["gh", "run", "view", run_id, "--job", job_id]
        proc = _run(view + ["--log-failed"])
        if not (proc.stdout or "").strip():
            proc = _run(view + ["--log"])
    else:
        jobs = _checks(platform, args.pr)
        match = next(
            (
                job
                for job in jobs
                if job.get("name") == args.job and _check_category(job) == "failed"
            ),
            None,
        )
        if match is None or match.get("id") is None:
            raise ReviewLoopError("failed job not found: {0}".format(args.job))
        proc = _run(["glab", "ci", "trace", str(match["id"])])
    tail = _log_tail(proc.stdout, args.lines)
    return {"job": args.job, "log_tail": tail, "empty": not bool(tail.strip())}


def command_comment(args):
    platform = _selected_platform(args)
    if platform == "github":
        _run(["gh", "pr", "comment"] + _ref_args(args.pr) + ["--body-file", args.body_file])
    else:
        viewed = _view(platform, args.pr)
        body = Path(args.body_file).read_text(encoding="utf-8")
        _glab_api_json(
            "POST",
            "projects/:id/merge_requests/{0}/notes".format(viewed["number"]),
            {"body": body},
        )
    return {"posted": True}


def command_set_section(args):
    platform = _selected_platform(args)
    viewed = _view(platform, args.pr)
    section_text = Path(args.file).read_text(encoding="utf-8")
    updated, replaced = replace_section(viewed["description"], section_text, args.heading)
    _write_description(platform, args.pr, viewed["number"], updated)
    return {"replaced": replaced}


def _utc_iso(moment):
    return moment.astimezone(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def command_push_time(args):
    platform = _selected_platform(args)
    viewed = _view(platform, args.pr)
    sha = viewed["head_sha"]
    if not sha:
        raise ReviewLoopError("PR/MR JSON is missing the head commit")
    created = None
    source = None
    if platform == "github":
        data = _json_command(
            ["gh", "api", "repos/{owner}/{repo}/commits/" + sha + "/check-suites"]
        )
        suites = data.get("check_suites") if isinstance(data, dict) else None
        stamps = [
            parse_utc_timestamp(suite["created_at"])
            for suite in suites or []
            if suite.get("created_at")
        ]
        if stamps:
            created, source = min(stamps), "check_suite"
        else:
            commit = _json_command(["gh", "api", "repos/{owner}/{repo}/commits/" + sha])
            committed = ((commit.get("commit") or {}).get("committer") or {}).get("date")
            if committed:
                created, source = parse_utc_timestamp(committed), "commit_date"
    else:
        # head_pipeline can still describe the previous push for a short
        # while; only trust it once it belongs to the current head commit.
        stamp = None
        for recheck in range(GITLAB_PIPELINE_RECHECKS + 1):
            if recheck:
                scaled_sleep(GITLAB_PIPELINE_RECHECK_SECONDS)
                viewed = _view(platform, args.pr)
            pipeline = viewed["_raw"].get("head_pipeline") or {}
            if (
                isinstance(pipeline, dict)
                and pipeline.get("sha") == sha
                and pipeline.get("created_at")
            ):
                stamp = pipeline["created_at"]
                break
        if stamp:
            created, source = parse_utc_timestamp(stamp), "pipeline"
        else:
            commit = _json_command(["glab", "api", "projects/:id/repository/commits/" + sha])
            committed = commit.get("committed_date")
            if committed:
                created, source = parse_utc_timestamp(committed), "commit_date"
    if created is None:
        raise ReviewLoopError("unable to determine push time")
    return {"head_sha": sha, "pushed_at": _utc_iso(created), "source": source}


def command_elapsed(args):
    start = parse_utc_timestamp(args.since)
    end = (
        parse_utc_timestamp(args.until)
        if args.until
        else datetime.datetime.now(datetime.timezone.utc)
    )
    return {"minutes": (end - start).total_seconds() / 60.0}


def _add_platform_args(parser, include_pr=True):
    parser.add_argument("--platform", choices=("github", "gitlab"))
    parser.add_argument("--url")
    if include_pr:
        parser.add_argument("--pr", help="PR/MR number, URL, or branch")


def _add_job_selection_args(parser):
    jobs = parser.add_mutually_exclusive_group()
    jobs.add_argument("--job")
    jobs.add_argument("--job-pattern", default=DEFAULT_JOB_PATTERN)


def build_parser():
    parser = JsonArgumentParser(description="Run mechanical GitHub/GitLab AI review-loop steps.")
    subparsers = parser.add_subparsers(dest="command")

    preflight = subparsers.add_parser("preflight", help="check CLI installation and authentication")
    preflight.add_argument("--platform", choices=("github", "gitlab"))
    source = preflight.add_mutually_exclusive_group()
    source.add_argument("--url")
    source.add_argument("--branch")
    preflight.set_defaults(func=command_preflight)

    detect = subparsers.add_parser("detect", help="detect the current PR/MR")
    _add_platform_args(detect)
    detect.set_defaults(func=command_detect)

    wait = subparsers.add_parser("wait", help="wait for and summarize review checks")
    _add_platform_args(wait)
    wait.add_argument("--minutes", type=float, required=True)
    wait.add_argument("--max-extensions", type=int, default=3)
    _add_job_selection_args(wait)
    wait.set_defaults(func=command_wait)

    rerun = subparsers.add_parser("rerun-review", help="rerun the selected review job")
    _add_platform_args(rerun)
    _add_job_selection_args(rerun)
    rerun.set_defaults(func=command_rerun_review)

    ensure = subparsers.add_parser("ensure-description", help="populate an empty description")
    _add_platform_args(ensure)
    ensure.add_argument("--template", required=True)
    ensure.set_defaults(func=command_ensure_description)

    fetch = subparsers.add_parser("fetch-review", help="poll for a matching review comment")
    _add_platform_args(fetch)
    fetch.add_argument("--since", required=True)
    fetch.add_argument("--pattern", default=DEFAULT_COMMENT_PATTERN)
    fetch.add_argument("--author")
    fetch.add_argument("--retries", type=int, default=5)
    fetch.add_argument("--interval", type=float, default=180)
    fetch.set_defaults(func=command_fetch_review)

    fetch_comments = subparsers.add_parser(
        "fetch-comments", help="fetch all new non-self PR/MR comments"
    )
    _add_platform_args(fetch_comments)
    fetch_comments.add_argument("--since", required=True)
    fetch_comments.add_argument("--exclude-author", action="append", default=[])
    fetch_comments.set_defaults(func=command_fetch_comments)

    parse = subparsers.add_parser("parse", help="parse review text from stdin")
    parse.set_defaults(func=command_parse)

    record = subparsers.add_parser("record", help="record or show learned review-loop settings")
    record.add_argument("--minutes", type=float)
    record.add_argument("--job")
    record.add_argument("--bot", help="login of the review bot that posts review comments")
    record.add_argument("--max-rounds", type=int)
    record.add_argument("--test-command")
    record.add_argument("--lint-command")
    record.add_argument("--local", action="store_true")
    record.add_argument("--tests", choices=("never", "serial"))
    record.add_argument("--agents")
    record.add_argument("--show", action="store_true")
    record.set_defaults(func=command_record)

    run_tests = subparsers.add_parser("run-tests", help="run tests through the machine-wide queue")
    run_tests.add_argument("--cmd")
    run_tests.add_argument("--timeout", type=float, default=3600)
    run_tests.set_defaults(func=command_run_tests)

    job_log = subparsers.add_parser("job-log", help="fetch the failed log for a named CI job")
    _add_platform_args(job_log)
    job_log.add_argument("--job", required=True)
    job_log.add_argument("--lines", type=int, default=200)
    job_log.set_defaults(func=command_job_log)

    comment = subparsers.add_parser("comment", help="post a PR/MR comment")
    _add_platform_args(comment)
    comment.add_argument("--body-file", required=True)
    comment.set_defaults(func=command_comment)

    section = subparsers.add_parser("set-section", help="replace a description section")
    _add_platform_args(section)
    section.add_argument("--file", required=True)
    section.add_argument("--heading", default="## AI Review Fixes")
    section.set_defaults(func=command_set_section)

    push_time = subparsers.add_parser("push-time", help="push time of the PR/MR head commit")
    _add_platform_args(push_time)
    push_time.set_defaults(func=command_push_time)

    elapsed = subparsers.add_parser("elapsed", help="minutes between two timestamps")
    elapsed.add_argument("--since", required=True)
    elapsed.add_argument("--until")
    elapsed.set_defaults(func=command_elapsed)
    return parser


def main(argv=None):
    args = None
    try:
        args = build_parser().parse_args(argv)
        if not hasattr(args, "func"):
            raise ReviewLoopError("a subcommand is required")
        result = args.func(args)
        exit_code = 0
        if isinstance(result, dict):
            exit_code = result.pop("_exit_code", 0)
        print(json.dumps(result, separators=(",", ":")))
        if args.command == "run-tests" and result.get("status") in ("failed", "timeout"):
            return EXIT_ERROR
        return exit_code
    except (ReviewLoopError, OSError, ValueError, re.error) as exc:
        result = {"error": str(exc)}
        stderr = getattr(exc, "stderr", None)
        if isinstance(exc, ReviewLoopError) and stderr:
            result["stderr"] = stderr
        print(json.dumps(result, separators=(",", ":")))
        return EXIT_ERROR


if __name__ == "__main__":
    sys.exit(main())
