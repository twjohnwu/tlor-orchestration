# Codex-first implementation flow (gondor-builder / dwarf-smith)

Read `~/.claude/agent_doc/codex-cli.md` first for shared invocation facts
and pitfalls; read `~/.claude/agent_doc/customize/builder-codex.md` too if
it exists.

Shared flow:

1. Check `command -v codex`; if absent, say nothing and do the work
   yourself — this must never error.
2. If present AND the dispatch does not say `no-codex`, compose a
   self-contained prompt and run
   `cd <repo root> && codex exec --sandbox workspace-write "<prompt>" </dev/null`
   (add `--skip-git-repo-check` outside a git repo).
3. Review codex's diff line by line; repair or redo any unfit work
   yourself.
4. State provenance in the report: codex-authored / codex+self-patched /
   fully self-written.
5. If files OUTSIDE the dispatch's ALLOWED PATHS appear modified after a
   codex run, do NOT revert them — parallel dispatches may own those
   changes; STOP and report the paths instead.

Role deltas:

- **gondor-builder**: compose the prompt FROM the dispatch (goal, context,
  acceptance criteria); review the diff against the ACCEPTANCE CRITERIA
  with ordinary engineering judgment.
- **dwarf-smith**: copy the exact recipe VERBATIM into the prompt; add no
  interpretation or variant. Measure every codex strike against the
  RECIPE; your role's step 3 binds codex too — an improvised non-fit is
  reverted or listed as skipped, exactly as if you forged it yourself.
