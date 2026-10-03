# Codex-first implement path (Maia-direct)

Read `~/.claude/agent_doc/codex-cli.md` first for shared invocation facts
and pitfalls; read `~/.claude/agent_doc/customize/builder-codex.md` too if
it exists — it extends and, where they disagree, overrides this one.

Audience: the Maia. Rule of record: `rules/dispatch.md` §3d. Since v0.13.0
the implement roles (`gondor-builder`, `dwarf-smith`) no longer call Codex
themselves; the Maia decides before dispatching.

## Flow

1. Once per session: `command -v codex`. Absent → skip this file for the
   session; dispatch the pinned role as usual.
2. Present, and the brief is not marked `no-codex` → take the pre-run
   snapshot (`git status --porcelain --untracked-files=all > <scratchpad>/pre.txt`,
   `git rev-parse HEAD`; if any path inside ALLOWED PATHS is already dirty in
   that snapshot, mark the brief `no-codex` — post-run attribution needs those
   files clean), write the brief exactly as you would for the
   role (goal, context, acceptance criteria, ALLOWED PATHS, STOP
   CONDITIONS, "do NOT commit"), then run it:
   `cd <repo root> && codex exec --sandbox workspace-write "$PROMPT" </dev/null`
   with `$PROMPT` built from a single-quoted heredoc, in the background.
   One codex attempt per subtask — never a second codex round. Never two
   codex jobs in one worktree at once, and no write-capable role dispatch
   in that worktree while codex runs.
3. Read back ONLY codex's final summary, `git status --porcelain`,
   `git diff --stat`, and `git rev-parse HEAD`. The full diff stays out of
   the main context; the working tree is the artifact.
4. Dispatch `eagle-sentinel` per dispatch.md §5 with the acceptance
   criteria and the working tree — never with codex's summary.
5. Fall back to the pinned role when ANY of: codex exits non-zero or
   reports STOP; HEAD moved (codex committed → STOP and report; the user
   decides); a path outside ALLOWED PATHS shows in
   `git status --porcelain --untracked-files=all` that was absent from the
   pre-run snapshot (STOP and report the paths — never revert:
   they may be the user's or a sibling dispatch's work); eagle-sentinel
   REFUTES; the task carries a step codex is known to skip (spec edits,
   fingerprint updates). Before dispatching the fallback: save codex's
   in-scope work with `git diff -- <ALLOWED PATHS> > <scratchpad>/codex-<subtask>.patch`,
   restore the ALLOWED PATHS files that were clean in the pre-run snapshot
   (leave files that were already dirty alone and list them), and carry
   `retry-of: codex — <what failed>; partial work saved at <patch>` in the
   brief. The fallback counts as the subtask's first role-tier attempt
   under dispatch.md §4.

## Brief shapes

- **gondor-shaped** (spec with acceptance criteria, local judgment OK):
  the brief is template §2 verbatim — goal, why, context, acceptance,
  do-not, non-goals, paths, stop conditions. Codex decides naming and
  structure within the neighboring style. If the task has an algorithmic
  sub-problem, the brief tells codex to read
  `~/.claude/agent_doc/algorithms/README.md` first and name the entry it used.
- **dwarf-shaped** (exact recipe, zero judgment): paste the recipe
  VERBATIM; add no interpretation or variant. Tell codex to list, not
  improvise, any site where the recipe does not fit.

## Mark `no-codex` when

- the change needs this session's MCP tools (codex has none);
- it touches institution files under `~/.claude/` (codex's shell is not
  covered by institution_guard, so this rule is honor-only — keep it);
- the Maia has already authored the edit verbatim within the cost-floor
  (dispatch.md §1) — do it inline instead;
- the task includes a mandatory step from codex-cli.md's pitfalls list.

## Provenance

State it in the commit message body or the PR description, one of:
`codex-authored`, `codex+role-patched`, `role-written`. Eagle's verdict
is the acceptance evidence either way.
