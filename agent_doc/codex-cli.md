# Codex CLI — shared invocation facts (all roles)

Read this when a dispatch (or your role file) sends work to the Codex CLI.
Machine-local specifics (companion-script paths, version-pinned flag
behavior) live in `~/.claude/agent_doc/customize/` — read any same-named
file there too; it extends and, where they disagree, overrides this one.

## Invocation

- Non-interactive one-shot, from the repo root:
  `codex exec --sandbox workspace-write "<prompt>" </dev/null`
  — the `</dev/null` is required; codex otherwise blocks on stdin. Outside
  a git repo add `--skip-git-repo-check`.
- Review mode: `codex review --uncommitted "<instructions>" </dev/null`
  (`--base <branch>` to compare against a branch).
- Omit `--sandbox workspace-write` for read-only work: the default sandbox
  cannot write the workspace.

## Prompt contract (operator style, one task per run)

- State the concrete job, the repo/failure context, and what done looks like.
- Give an exact output contract (shape and brevity).
- Coding/debug tasks: require a verification loop — run commands, quote
  output, STOP and report after 2 failed attempts, never fabricate a pass.
- Write tasks: enumerate allowed paths and forbidden files; no commits, no
  new dependencies unless granted.

## Pitfalls (field-proven)

- NEVER pass a prompt in double quotes from zsh — a backtick inside it runs
  as command substitution on YOUR machine before codex ever sees it. Build
  the prompt with a single-quoted heredoc (`PROMPT=$(cat <<'HEREDOC' ...`)
  and pass `"$PROMPT"`.
- The sandbox has NO network: dependency fetches (a first cargo build, npm
  install) must be run by the orchestrator outside codex.
- Sandbox process spawn is slow: never retune production timeouts or
  constants to make tests pass inside the sandbox — use a test-only
  override and say so in the report.
- Codex silently skips steps it deems out of scope; anything mandatory
  (spec edits, fingerprint updates) stays OUT of codex prompts and goes to
  a tlor role instead.
