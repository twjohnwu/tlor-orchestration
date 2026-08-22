# Rules & hooks

[← Back to README](../../README.md)

## Rules

The plugin bundles depersonalized orchestration rules. Install them with
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

You can also drop your own `.md` rule files into `rules/customize/`. They
auto-load natively (the same `.claude/rules/` mechanism as everything else
here, no routing table required), and the installer will never touch them.
The routing table `/tlor-init` generates does nothing more than advertise
this directory to tools that read AGENTS.md but know nothing about
`.claude/rules/`; it is not what makes the files load.

## Agent docs (agent_doc/, lazy-load)

Role-specific reference docs that load on a condition. A dispatched subagent
Reads them only when its trigger fires (a codex-capable machine, a JS-only
page, a HIGH-RISK verdict), so the text costs nothing in every other
dispatch. The division of labor: rules/ holds what EVERY context must know,
agent_doc/ holds what one role needs sometimes.

| Sublayer | Owner | Install behavior |
|---|---|---|
| `agent_doc/*.md` | plugin | overwritten on every install/upgrade |
| `agent_doc/<lang>/*.md` (e.g. `zh_tw/`, `en_us/`) | plugin | exactly one level of language/topic subdirectory, discovered generically (any dir except `customize/`); overwritten on every install/upgrade, uninstalled per-file same as the flat files |
| `agent_doc/customize/` | user | copied only if absent (behind `--with-optional`), survives uninstall; a file here at the same RELATIVE path as a base file is read IN ADDITION to it and wins where they disagree |

| Doc | Read by | Trigger |
|---|---|---|
| `codex-cli.md` | any role calling the Codex CLI | before composing a codex invocation |
| `builder-codex.md` | gondor-builder, dwarf-smith | codex present and the dispatch does not say `no-codex` |
| `eagle-codex-prescreen.md` | eagle-sentinel | HIGH-RISK verdict + codex present + no `no-codex` |
| `noldor-browser.md` | noldor-loremaster | WebFetch returns a JS-only shell; also holds the bot-verifier (CAPTCHA) leave-the-browser-open protocol |
| `bilbo-scribe.md` | bilbo-scribe | FIRST step of every dispatch — routing table + shared writing core (six-step workflow, five-dimension self-score, fact preservation) |
| `zh_tw/patterns.md`, `zh_tw/style.md`, `zh_tw/localization.md` | bilbo-scribe | output/target language is zh-TW |
| `en_us/patterns.md`, `en_us/style.md` | bilbo-scribe | output/target language is English |
| `seo-writing.md` | bilbo-scribe | task is SEO / search-oriented content |
| `tone-development.md` | bilbo-scribe | task asks to develop or apply a specific brand/author tone |
| `user-guide-ste.md` | bilbo-scribe | task is a user guide / operating manual / step-by-step doc |
| `scene-calibration.md` | bilbo-scribe | writing a NEW piece (always), or editing when a target platform/genre is named |

`institution_guard` protects `~/.claude/agent_doc/` the same way it protects
rules/ and agents/: main-session edits are denied, dispatched subagents pass.

## Hooks (opt-in)

All four hooks are **silent by default**: an environment variable turns on
the first three, registration turns on the fourth. Every one of them fails
open on an internal error, so the call goes through and a bug in a hook never
blocks your work. `install.sh` copies the hook scripts but does not wire or
activate them (no `hooks.json`, no env vars) — use the plugin route for that.

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
