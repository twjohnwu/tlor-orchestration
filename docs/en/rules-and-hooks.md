# Rules & hooks

[← Back to README](../../README.md)

## Rules

The plugin bundles depersonalized orchestration rules — install them via
`/tlor-init` or `install.sh`:

**Required** (6 files, plugin-owned — unconditionally overwritten on every
install/upgrade, `version` stamped from `.claude-plugin/plugin.json`, no
`## Lessons` section — see the ownership model in
[installation.md](installation.md)):

| Rule | Purpose |
|---|---|
| `dispatch.md` | Role dispatch table, delegation contract, escalation paths, verification rules |
| `decomposition.md` | How to split tasks into dispatches (parallel vs sequential, sizing) |
| `delegation-templates.md` | Fill-in prompt templates for each dispatch type |
| `judgment.md` | When to escalate, when done, when to ask, wrong-direction signals |
| `risk-tiers.md` | Classify actions by risk (T1 irreversible / T2 hard-to-undo / T3 reversible) |
| `maintenance.md` | What sessions may change vs what needs human approval |

**Optional** (6 files, living in `rules/customize/` — install with
`--with-optional` or choose in `/tlor-init`; once copied, never overwritten):

| Rule | Purpose |
|---|---|
| `design-principles.md` | 7 fallback principles for uncovered cases (P1-P7) |
| `user-decision-patterns.md` | 3 decision patterns for AI-assisted development (D1-D3) |
| `judgment.md` | Compact-MADR candidate-comparison format + a "General decisions log" that accumulates cross-project decisions (base `judgment.md` §5 points here) |
| `letter-to-future-sessions.md` | Blank template — fill in over time with project facts, decay countermeasures, honest limits |
| `skill-triggers.md` | When to invoke a skill instead of following a blanket "always invoke" injection — fill in your installed plugins' namespace priority |
| `lessons.md` | Append-only recurring-workflow-failure log, one section per base rule file |

You can also drop your own `.md` rule files into `rules/customize/` — they
auto-load natively (the same `.claude/rules/` mechanism as everything else
here, no routing table required), and the installer will never touch them.
The routing table `/tlor-init` generates just documents this directory for
tools that read AGENTS.md but don't know about `.claude/rules/` — it isn't
what makes the files load.

## Hooks (opt-in)

All four hooks are **silent by default** — the first three are enabled by an
environment variable, the fourth by registration. Every one of them fails open
on an internal error (the call goes through; work is never blocked by a bug).
`install.sh` copies the hook scripts but does not wire or activate them
(no `hooks.json`, no env vars); use the plugin route for that.

| Hook | Event | What it does | Env key |
|---|---|---|---|
| `institution_guard` | PreToolUse | Blocks the main session from Edit/Write on institution files (`~/.claude/institution/`, `rules/`, `agents/`, and any `CLAUDE.md`/`AGENTS.md` anywhere) — enforces "the commander doesn't do field work"; subagent edits pass through | `TLOR_INSTITUTION_GUARD=1` |
| `dispatch_guard` | PreToolUse | Denies dispatches to `general-purpose`/`claude`/`explore`/`plan`; `bombadil-freeagent` passes only when its prompt carries a `no-role-fits` mention (model/effort are pinned in its frontmatter; a per-call `model` override stays optional) | `TLOR_DISPATCH_GUARD=1` |
| `verify_gate` | Stop | Catches "done" claims with no evidence: if code files were edited this turn and no test command was run, it blocks the turn once, asking for fail-then-pass evidence | `TLOR_VERIFY_GATE=1` |
| `stdd_test_guard` | PreToolUse | STDD execute-phase protection: a test file cited by a `[wip]` task in `tasks.md` cannot be edited or rewritten until that task is marked `[x]` | none — registered into `settings.json` by `install.sh --install-hook` |

Three notes:

- **The three PreToolUse hooks are chained.** `hooks.json` wires only
  `pre_tool_use.sh`, which runs `institution_guard.py` first and
  **short-circuits if it produced output**; `dispatch_guard.py` runs only when
  it did not.
- **The bash fallback needs jq.** With no `python3` present the guard falls
  back to `institution_guard.sh`, which depends on `jq`; without `jq` it
  silently passes everything through.
- **`TLOR_STDD_ALLOW_TEST_REWRITE=1` is a bypass, not a switch.** It lifts
  `stdd_test_guard`'s block for one call (plan-drift recovery); it enables
  nothing.

### Session-snapshot caveat

Claude Code reads PreToolUse hooks from `settings.json` once, at session
start — running `--install-hook` (or otherwise registering a hook)
inside an existing or `--continue`/`--resume`d session will NOT activate the
hook there. Verify any newly-registered hook in a brand-new session only.
