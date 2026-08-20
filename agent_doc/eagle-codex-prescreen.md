# Codex pre-screen before a council recommendation (eagle-sentinel)

Preconditions — ALL must hold, otherwise skip the pre-screen silently: the
verdict is heading into HIGH-RISK territory; `command -v codex` succeeds;
the dispatch does not say `no-codex`. See `~/.claude/agent_doc/codex-cli.md`
for shared invocation pitfalls; read
`~/.claude/agent_doc/customize/eagle-codex-prescreen.md` too if it exists.

Procedure:

1. From the repo root run
   `codex review --uncommitted "<review instructions>" </dev/null`
   (`--base <branch>` when comparing against a branch; add
   `--skip-git-repo-check` outside a git repo).
2. The review instructions MUST embed the dispatch's acceptance criteria
   verbatim plus scope, and MUST NOT include the producer's
   summary/reasoning.
3. Confirm or refute every codex finding YOURSELF — never cite codex's
   words as evidence.
4. A CONFIRMED blocking defect sends the verdict straight to REFUTED and
   skips the council; otherwise proceed to the council recommendation in
   your role file, attaching the screen results with each item labeled
   `codex-flagged` / `eagle-confirmed` / `eagle-refuted`.
