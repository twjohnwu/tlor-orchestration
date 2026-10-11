# -*- coding: utf-8 -*-
"""
Test queue guard — an OPT-IN PreToolUse hook (silent unless
TLOR_TEST_QUEUE_GUARD=1).

Enforces the per-machine test policy of stdd-review-loop. The policy lives in
`<repo root>/AGENTS.local.md` (gitignored, per machine), under `## Review loop`:
`- tests: never` denies every test-like Bash command; `- tests: serial` allows
tests only through the queue (`review_loop.py run-tests`), foreground. No
`tests` key, or an unknown value, means the repo/machine is untouched.

The command is split into segments (`;` `&&` `||` `|` `&` newline `(` `)`)
by a quote-aware tokenizer: quoted text, comments, and heredoc bodies never
form a segment. Each segment loses leading wrappers (`VAR=val`, `env`,
`timeout N`, `nice`, `time`, `nohup`, `command`, `exec`, `uv run`,
`poetry run`, `pipenv run`, `bundle exec`, `npx`, `pnpm exec`, `yarn exec`);
`bash|sh|zsh -c "<string>"` is classified recursively. A segment is test-like
when its first word is a test runner (see _is_test_segment) or it equals the
`test-command` from the repo's AGENTS.md; it is queued when it is
`python* <path>/review_loop.py run-tests`. Fails open on any error — the
guard must never break a session.
"""
import json
import os
import re
import shlex
import sys

if os.environ.get("TLOR_TEST_QUEUE_GUARD") != "1":
    sys.exit(0)

_OPERATORS = ("&&", "||", ";;", "|&", ";", "|", "&", "(", ")")
_REDIRECTS = ("<<<", "<<-", "<<", ">>", ">&", "<&", "&>", ">|", "<>", ">", "<")
_DIRECT_RUNNERS = {
    "pytest", "py.test", "tox", "nox", "jest", "vitest", "mocha", "rspec",
    "phpunit", "ctest",
}
_SHELLS = {"bash", "sh", "zsh", "dash", "ksh"}
_PYTHON = re.compile(r"^python[0-9.]*$")
_ASSIGNMENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")
# Wrapper options that consume the next word.
_ARG_OPTIONS = {
    "env": {"-u", "--unset", "-C", "--chdir", "-S"},
    "timeout": {"-s", "--signal", "-k", "--kill-after"},
    "nice": {"-n", "--adjustment"},
    "exec": {"-a"},
    "uv": {"--with", "--python", "-p", "--project", "--directory", "--package",
           "--extra", "--group", "--env-file", "--with-requirements"},
    "npx": {"-p", "--package", "-c", "--call"},
}
# Package-manager options that consume the next word (`pnpm --filter web
# test`, `npm --prefix web test`). `-w` takes a value only for npm; for pnpm it
# is the boolean --workspace-root, so `pnpm -w test` stays a test run.
_PM_VALUE_OPTIONS = {"--prefix", "-C", "--dir", "--filter", "-F", "--cwd", "--workspace"}
_PM_ARG_OPTIONS = {
    "npm": _PM_VALUE_OPTIONS | {"-w"},
    "pnpm": _PM_VALUE_OPTIONS,
    "yarn": _PM_VALUE_OPTIONS,
    "bun": _PM_VALUE_OPTIONS,
}
# Shell keywords and grouping that may precede the real command in a segment
# (`for ...; do pytest; done`, `{ pytest; }`, `! pytest`). Header words
# (for/while/if/until/case) are deliberately not listed: a header is not a run.
_KEYWORDS = {"do", "then", "else", "elif", "{", "!", "time"}
_MAX_DEPTH = 5


def _tokenize(command):
    """Quote-aware shell tokenizer: a list of ("word", text) and ("op", text).
    Newline is an operator; comments and heredoc bodies are dropped; an
    unterminated quote just ends the word."""
    tokens = []
    heredocs = []
    word = []
    in_word = False
    expect_heredoc = None
    i = 0
    n = len(command)

    def finish():
        if in_word:
            text = "".join(word)
            if expect_heredoc is not None:
                heredocs.append((text, expect_heredoc))
                return None
            tokens.append(("word", text))
        return None

    while i < n:
        ch = command[i]
        if ch in " \t\r":
            finish()
            if in_word and expect_heredoc is not None:
                expect_heredoc = None
            word, in_word = [], False
            i += 1
            continue
        if ch == "\\" and i + 1 < n:
            if command[i + 1] == "\n":
                i += 2
                continue
            word.append(command[i + 1])
            in_word = True
            i += 2
            continue
        if ch == "'":
            close = command.find("'", i + 1)
            close = n if close < 0 else close
            word.append(command[i + 1:close])
            in_word = True
            i = close + 1
            continue
        if ch == '"':
            i += 1
            while i < n and command[i] != '"':
                if command[i] == "\\" and i + 1 < n and command[i + 1] in '"\\$`\n':
                    i += 1
                word.append(command[i])
                i += 1
            in_word = True
            i += 1
            continue
        if ch == "#" and not in_word:
            while i < n and command[i] != "\n":
                i += 1
            continue
        if ch == "\n":
            finish()
            if in_word and expect_heredoc is not None:
                expect_heredoc = None
            word, in_word = [], False
            tokens.append(("op", "\n"))
            i += 1
            # Skip pending heredoc bodies up to their delimiter lines.
            while heredocs:
                delimiter, strip_tabs = heredocs.pop(0)
                while i < n:
                    end = command.find("\n", i)
                    end = n if end < 0 else end
                    line = command[i:end]
                    i = end + 1
                    if (line.lstrip("\t") if strip_tabs else line) == delimiter:
                        break
            continue
        redirect = next((r for r in _REDIRECTS if command.startswith(r, i)), None)
        if redirect is not None:
            finish()
            if in_word and expect_heredoc is not None:
                expect_heredoc = None
            word, in_word = [], False
            i += len(redirect)
            if redirect in ("<<", "<<-"):
                expect_heredoc = redirect == "<<-"
            else:
                tokens.append(("redirect", redirect))
            continue
        operator = next((o for o in _OPERATORS if command.startswith(o, i)), None)
        if operator is not None:
            finish()
            word, in_word = [], False
            expect_heredoc = None
            tokens.append(("op", operator))
            i += len(operator)
            continue
        word.append(ch)
        in_word = True
        i += 1
    finish()
    return tokens


def _segments(command):
    """List of (words, separator after it) for each simple command. A `&`
    right after a `( ... )` group backgrounds every segment inside it."""
    segments = []
    words = []
    skip_target = False
    groups = []
    closed = None
    for kind, text in _tokenize(command):
        if kind == "redirect":
            skip_target = True
            closed = None
        elif kind == "word":
            closed = None
            if skip_target:
                skip_target = False
            else:
                words.append(text)
        else:
            skip_target = False
            if text == "&" and closed is not None:
                for index in range(closed[0], closed[1]):
                    segments[index] = (segments[index][0], "&")
            closed = None
            segments.append((words, text))
            words = []
            if text == "(":
                groups.append(len(segments))
            elif text == ")" and groups:
                closed = (groups.pop(), len(segments))
    segments.append((words, ""))
    return [(w, sep) for w, sep in segments if w]


def _base(word):
    return os.path.basename(word)


def _drop_options(words, name):
    takes_arg = _ARG_OPTIONS.get(name, set())
    while words and words[0].startswith("-") and words[0] != "-":
        option = words.pop(0)
        if option == "--":
            break
        if option in takes_arg and words:
            words.pop(0)
    return words


def _strip_wrappers(words):
    """Drop leading wrappers; return (words, inner shell string or None)."""
    words = list(words)
    while words:
        first = _base(words[0])
        second = words[1] if len(words) > 1 else ""
        if _ASSIGNMENT.match(words[0]):
            words.pop(0)
        elif words[0] in _KEYWORDS:
            words.pop(0)  # shell keyword / grouping at segment start
        elif first == "env":
            words = _drop_options(words[1:], "env")
            while words and _ASSIGNMENT.match(words[0]):
                words.pop(0)
        elif first == "timeout":
            words = _drop_options(words[1:], "timeout")
            if words:
                words.pop(0)  # the duration
        elif first in ("nice", "time", "nohup", "exec"):
            words = _drop_options(words[1:], first)
        elif first == "command":
            if second in ("-v", "-V"):
                return [], None  # a lookup, not a run
            words = _drop_options(words[1:], first)
        elif first in ("uv", "poetry", "pipenv") and second == "run":
            words = _drop_options(words[2:], first)
        elif first == "bundle" and second == "exec":
            words = _drop_options(words[2:], first)
        elif first in ("pnpm", "yarn") and second == "exec":
            words = _drop_options(words[2:], first)
        elif first == "npx":
            words = _drop_options(words[1:], "npx")
        elif first in _SHELLS:
            rest = words[1:]
            while rest and rest[0].startswith("-") and rest[0] != "-":
                flags = rest.pop(0)
                if not flags.startswith("--") and "c" in flags[1:]:
                    return [], rest[0] if rest else ""
            return words, None
        else:
            break
    return words, None


def _first_arg(words):
    return next((w for w in words if not w.startswith(("-", "+"))), "")


def _pm_positionals(name, words):
    """Non-option words of a package-manager command line, skipping the
    values of its value-taking options; `yarn workspace <name>` is dropped."""
    takes_arg = _PM_ARG_OPTIONS[name]
    positionals = []
    index = 0
    while index < len(words):
        word = words[index]
        if word.startswith(("-", "+")):
            index += 2 if word in takes_arg else 1
            continue
        positionals.append(word)
        index += 1
    if name == "yarn" and positionals[:1] == ["workspace"]:
        positionals = positionals[2:]
    return positionals


def _is_test_segment(words):
    if not words:
        return False
    first = _base(words[0])
    rest = words[1:]
    if first in _DIRECT_RUNNERS:
        return True
    if _PYTHON.match(first):
        for index, word in enumerate(rest):
            if not word.startswith("-"):
                return False
            if word == "-m":
                return index + 1 < len(rest) and rest[index + 1] in ("pytest", "unittest")
            if word.startswith("-m"):
                return word[2:] in ("pytest", "unittest")
        return False
    if first in ("go", "cargo", "swift", "dotnet"):
        return _first_arg(rest) == "test"
    if first in ("mvn", "mvnw", "gradle", "gradlew"):
        return any(w == "test" or w.endswith(":test") for w in rest)
    if first in _PM_ARG_OPTIONS:
        args = _pm_positionals(first, rest)
        arg = args[0] if args else ""
        if arg in ("test", "t"):
            return True
        if arg in ("run", "run-script"):
            return len(args) > 1 and args[1].startswith("test")
        return first in ("yarn", "pnpm") and arg in ("jest", "vitest")
    if first in ("make", "gmake"):
        return any(
            w.startswith(("test", "check")) for w in rest
            if not w.startswith("-") and "=" not in w
        )
    if first == "xcodebuild":
        return any(w in ("test", "test-without-building") for w in rest)
    return False


def _is_queued_segment(words):
    if not words or not _PYTHON.match(_base(words[0])):
        return False
    rest = [w for w in words[1:]]
    while rest and rest[0].startswith("-"):
        rest.pop(0)
    return (
        len(rest) >= 2
        and rest[0].endswith("review_loop.py")
        and rest[1] == "run-tests"
    )


def _normalized(text):
    return [w for segment, _ in _segments(text) for w in segment] if text else []


def _classify(command, test_words, depth=0):
    """Yield (test_like, queued, backgrounded) for every simple command."""
    for words, separator in _segments(command):
        stripped, inner = _strip_wrappers(words)
        if inner is not None:
            if depth < _MAX_DEPTH:
                for test, queued, bg in _classify(inner, test_words, depth + 1):
                    yield test, queued, bg or separator == "&"
            continue
        matches_command = bool(test_words) and test_words in (words, stripped)
        yield (
            matches_command or _is_test_segment(stripped),
            _is_queued_segment(stripped),
            separator == "&",
        )


def _find_root(cwd):
    path = os.path.abspath(cwd or os.getcwd())
    while True:
        if os.path.exists(os.path.join(path, ".git")):
            return path
        parent = os.path.dirname(path)
        if parent == path:
            return path
        path = parent


def _read(path):
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return fh.read()
    except OSError:
        return ""


def _section_value(path, key):
    """Value of `- <key>: value` inside the `## Review loop` section of a
    file (same format review_loop.py reads), or None."""
    text = _read(path)
    head = re.search(r"(?m)^## Review loop[ \t]*\r?$", text)
    if not head:
        return None
    rest = text[head.end():]
    following = re.search(r"(?m)^##\s+", rest)
    section = rest[: following.start()] if following else rest
    match = re.search(r"(?m)^- " + re.escape(key) + r":[ \t]*(.*?)[ \t]*\r?$", section)
    return match.group(1) if match else None


def _queue_script():
    """Absolute path of review_loop.py for the deny message: the installed
    skill, else the copy next to this hook in the plugin repo, else a
    placeholder."""
    here = os.path.dirname(os.path.abspath(__file__))
    candidates = (
        os.path.expanduser("~/.claude/skills/stdd-review-loop/references/review_loop.py"),
        os.path.join(here, "..", "stdd-skills", "stdd-review-loop", "references", "review_loop.py"),
    )
    for candidate in candidates:
        if os.path.isfile(candidate):
            return shlex.quote(os.path.normpath(candidate))
    return "<path>/review_loop.py"


def _deny(reason):
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": reason,
        }
    }, ensure_ascii=False))


def main():
    try:
        data = json.loads(sys.stdin.read() or "{}")
        if data.get("tool_name", "") != "Bash":
            return 0
        tool_input = data.get("tool_input", {}) or {}
        command = tool_input.get("command", "") or ""
        if not isinstance(command, str):
            return 0

        root = _find_root(data.get("cwd"))
        tests = _section_value(os.path.join(root, "AGENTS.local.md"), "tests")
        if tests not in ("never", "serial"):
            return 0

        test_command = _section_value(os.path.join(root, "AGENTS.md"), "test-command")
        test_words = _normalized(test_command)
        whole = bool(test_words) and _normalized(command) == test_words
        items = list(_classify(command, test_words))
        if tests == "never":
            if whole or any(test or queued for test, queued, _ in items):
                _deny(
                    "tlor test_queue_guard: tests disabled on this machine for "
                    "this repo (AGENTS.local.md `tests: never`)."
                )
            return 0

        if any(queued and (bg or tool_input.get("run_in_background"))
               for _, queued, bg in items):
            _deny("tlor test_queue_guard: test queue runs foreground only "
                  "(drop run_in_background).")
            return 0
        if whole or any(test and not queued for test, queued, _ in items):
            _deny(
                "tlor test_queue_guard: tests on this machine run one at a "
                "time through the queue (AGENTS.local.md `tests: serial`). Use "
                "`python3 " + _queue_script() + " run-tests --cmd '"
                + command.replace("'", "'\\''") + "' --timeout 240`, "
                "foreground, with the "
                "Bash tool timeout set to 600000."
            )
    except Exception:
        pass  # fail-open: guard failure must never block a session
    return 0


if __name__ == "__main__":
    sys.exit(main())
