---
name: tlor-init
description: 'Installer ritual — sets up or upgrades the tlor-orchestration framework (agents, rules, CLAUDE.md/AGENTS.md routing, optional hooks). Run explicitly via `/tlor-init`.'
disable-model-invocation: true
---

# /tlor-init — Orchestration Framework Setup

Initialize or upgrade the tlor-orchestration orchestration framework. Installs agent
roles, dispatch rules, CLAUDE.md/AGENTS.md routing, and optional guard hooks.

## Workflow

### Step 1: Detect existing installation

Scan for existing tlor-orchestration files:

```bash
# Check common locations for existing agents
for dir in ~/.claude/agents .claude/agents agents; do
  if [ -d "$dir" ] && ls "$dir"/rohirrim-outrider.md 2>/dev/null; then
    echo "Found existing installation at: $dir"
  fi
done
```

If found, compare `version:` frontmatter in each installed file against the
bundled versions in the plugin. List any files with version differences:

| File | Installed | Bundled | Action needed |
|------|-----------|---------|---------------|
| (name) | (local ver) | (plugin ver) | update/skip |

This version comparison is orientation only — a quick heads-up for what's
likely to change. The authoritative per-file decision is Step 3's `cmp -s`
byte comparison, not this version-string diff (a version bump with no
content change, or a hand-edit with no version bump, both fall through to
whatever Step 3 actually finds).

### Step 2: Choose installation level

Ask the user which installation level to use:

- **User level** (`~/.claude/`): agents at `~/.claude/agents/`, rules at
  `~/.claude/rules/`, CLAUDE.md at user root — available to ALL projects
- **Project level** (`.claude/`): agents at `.claude/agents/`, rules at
  `.claude/rules/`, CLAUDE.md at project root — scoped to this project
- **Repo level**: direct copy to user-specified paths — maximum flexibility

Do NOT cross-contaminate levels. User-level install does not touch project files.

### Step 3: Set up the institution layout and install agents

For a **User level** install only (`~/.claude/`), first make the layout
idempotent so this and future installs never clobber a directory the user
relocated by hand. Apply this 3-branch check to each of
`~/.claude/agents`, `~/.claude/rules`, `~/.claude/hooks`:

1. **Already a symlink** → skip, nothing to do.
2. **A real directory exists** → move it to `~/.claude/institution/<name>/`,
   then symlink `~/.claude/<name>` to it (so nothing already there is lost).
3. **Missing** → create `~/.claude/institution/<name>/` and symlink
   `~/.claude/<name>` to it.

(Project/repo level installs use plain directories — this institution layout
is a `~/.claude/` concept only.)

Then install the 12 agent role definitions from the plugin's `agents/`
directory to `<target>/agents/`:

- rohirrim-outrider.md
- ranger-pathfinder.md
- noldor-loremaster.md
- dwarf-smith.md
- gondor-builder.md
- eagle-sentinel.md
- elf-archer.md
- orc-saboteur.md
- hobbit-gardener.md
- mirror-of-galadriel.md
- palantir-stone.md
- cirdan-shipwright.md

**Agent files use backup-and-overwrite, not a silent unconditional
overwrite.** Agent frontmatter supports no import mechanism, so a user's
local edit (the motivating case: extending a role's `tools:` line to add an
MCP server) has nowhere to live except the installed file itself. An
unconditional overwrite with no trace left behind (as base rules use, Step
4) would destroy that edit with no way to recover it.

`install.sh` is the single source of truth for the actual per-file algorithm
(its agent-role loop: missing → install, `cmp -s` identical → unchanged,
different → back up to `<file>.bak-YYYYMMDD-HHMMSS` next to itself, then
overwrite) — don't re-derive or re-narrate it here; run `./install.sh
--dry-run` to preview exactly what it will do for the current installation
before applying it for real. The `.bak-YYYYMMDD-HHMMSS` copy is the user's
source for re-applying any customization by hand afterward — tell them
plainly which file was backed up and where.

Report each file's outcome (installed / updated-with-backup / unchanged)
for Step 12's summary.

### Step 4: Install required rules

Base rules are **plugin-owned**: copy the 6 required rule files from the
plugin's `rules/` directory to `<target>/rules/` as an **unconditional
overwrite** — no version-compare-and-ask here, the plugin is the single
source of truth for these files. While copying, inject a `version: <plugin
version>` line into each file's frontmatter (reading the version from the
plugin's `.claude-plugin/plugin.json`, not from the shipped file itself).
This is intentionally different from Step 3's agent-file handling: base
rules have zero user-writable sections by design (`rules/customize/` is
where user content goes instead, Step 5/7), so there is nothing to preserve
and no conffile/merge machinery applies here — see docs/en/installation.md's
"Ownership model" section, which documents this as a stated invariant, not
an oversight.

- dispatch.md — role dispatch table, delegation rules, escalation paths,
  plan mode dispatch table requirements
- decomposition.md — how to split tasks into dispatches
- delegation-templates.md — fill-in prompt templates for subagent dispatch
- judgment.md — when to escalate, when done, when to ask
- risk-tiers.md — classify actions by risk before executing
- maintenance.md — what's safe to change vs needs user approval

None of these 6 files carry a `## Lessons` section of their own — they're
overwritten unconditionally on every upgrade, so anything appended there
would be wiped. Recurring workflow lessons instead go in
`rules/customize/lessons.md` (see Step 5).

### Step 5: Offer optional rules

Ask the user whether to install optional rules from `rules/customize/` in the
plugin bundle:

- **design-principles.md** — 7 fallback principles for uncovered cases (P1-P7)
- **user-decision-patterns.md** — 3 decision patterns for AI-assisted development (D1-D3)
- **customize/judgment.md** — compact-MADR candidate-comparison format plus
  a "General decisions log" section that accumulates the user's
  cross-project decisions; base `rules/judgment.md` §5 carries a
  conditional pointer to it.
- **customize/letter-to-future-sessions.md** — a blank template the user
  fills in over time (non-obvious project facts, decay countermeasures,
  honest limits); ships empty on purpose.
- **customize/skill-triggers.md** — when to invoke a skill instead of
  following a blanket "always invoke" injection; ships with a
  placeholder namespace-priority table. After installing, guide the user to
  fill it in with the plugins they actually have installed — that table
  can't be filled in generically at build time.
- **customize/lessons.md** — the append-only log for recurring workflow
  lessons, one `##` section per base rule file; ships with empty sections.
- **customize/output-calibration.md** — the two output rules that live
  nowhere else: how long a written deliverable on disk should be, and the
  five things brevity must never trim (skipped/unverified work, quoted
  verification output, `file:line` evidence, assumptions acted on, and T1
  actions).

These provide design philosophy guidance. The framework works without them.
If installed, copy them to `<target>/rules/customize/`. Per the ownership
model below, only copy a file if it does not already exist at the
destination — never overwrite something already in `customize/`.

### Step 6: STDD 視角選擇 (opt-in)

Ask the user which STDD 視角 (perspective) to install, or to skip:

- **RD** — stdd-plan, stdd-execute, stdd, stdd-lint (**deferred this round**)
- **PM** — stdd-explore, stdd-spec, stdd, stdd-lint (**deferred this round**)
- **UIUX** — stdd-explore, stdd-uiux, stdd, stdd-lint (**deferred this round**)
- **ALL** — all 7 skills under the plugin's `stdd-skills/` directory
  (discover the list dynamically — `ls stdd-skills/`, don't hardcode a count)
- **skip** — install no STDD skills (default; keeps this step backward
  compatible with users who never asked for STDD)

If the user picks **RD**, **PM**, or **UIUX**: tell them plainly "此視角
deferred，本輪僅支援 ALL" and install nothing for that choice — never
silently fall back to installing some other subset.

If the user picks **ALL**: copy each `stdd-skills/<name>/` directory from
the plugin bundle to `<target>/skills/<name>/` (same copy style as Step 3's
agent roles). Then record the choice in `<target>/skills/.tlor-stdd-manifest`
— first line `role=ALL`, remaining lines the installed skill dir names (this
mirrors `install.sh`'s manifest style, so `/tlor-restore`-style tooling can
read it the same way).

**Re-running this step** (upgrade or reconfigure) SHALL allow the user to
change 視角:
- **Additions** (switching to a 視角 that needs more skills than currently
  installed) are incremental — copy only the newly-needed skill dirs, leave
  existing ones alone.
- **Removals** (switching to a 視角 that needs fewer skills, or to `skip`)
  SHALL NOT happen silently — list exactly which skill dirs would be
  removed and ask for explicit confirmation first.
- **`[wip]` guard on removing `stdd-execute`**: if the removal set contains
  `stdd-execute`, first scan every `STDD/<name>/tasks.md` in the current
  project for `[wip]` or unchecked `[ ]` tasks. If any are found, warn the
  user and require explicit confirmation before proceeding — suggested
  wording (per specs/stdd-integration.md S-34): "偵測到 N 個 change 有未完成
  任務，移除 `stdd-execute` 後將無法繼續該 change 的 execute 流程，建議先
  恢復/完成後再切換——是否仍要繼續？" Only remove `stdd-execute` after the
  user confirms.

### Step 7: Create the customize directory

Ensure `<target>/rules/customize/` exists at the install destination:

- If Step 5 installed optional rules, this directory already exists — nothing
  further to do.
- If the user skipped Step 5, create the empty directory anyway.

This is the landing zone for the user's own project- or team-specific rules,
and the only place user content lives — **the installer never overwrites
anything already in `customize/`**, no matter how it got there (Step 5
optional copy, or the user's own files). Explain to the user: a `.claude/rules/`
directory (and `~/.claude/rules/` at user level) is a native Claude Code
auto-load location — any `.md` file placed there, `customize/` included,
loads automatically at session start, no routing wiring needed, just drop the
file in. The routing table's catch-all row (Step 8) documents this for
readers of AGENTS.md; it is not what makes the file load.

### Step 8: Set up CLAUDE.md + AGENTS.md routing

Generate TWO files (replace `<rules-path>` with the actual path, e.g.
`.claude/rules` for project level).

**CLAUDE.md** (thin router, <20 lines):

```
@AGENTS.md

## Non-negotiable rules
1. Delegate, don't do. (→ rules/dispatch.md)
2. Verify before claiming done. (→ rules/dispatch.md §5)
3. Plan mode uses dispatch.md roles. (overrides built-in search default)
```

**AGENTS.md** (routing + agent priority):

```
# AGENTS.md — tlor-orchestration orchestration

## Agent routing priority
This environment uses tlor-orchestration roles as the PRIMARY dispatch targets.
If other plugins provide agents with similar functions, prefer tlor-orchestration
roles unless the user explicitly names another plugin's agent.

## Routing table
| Situation | Read first |
|---|---|
| Dispatching subagents, model/effort, escalation, verification | <rules-path>/dispatch.md |
| Splitting a task into dispatches | <rules-path>/decomposition.md |
| Writing a delegation prompt | <rules-path>/delegation-templates.md |
| Unsure: escalate? done? ask user? wrong direction? | <rules-path>/judgment.md |
| Classifying action risk before executing | <rules-path>/risk-tiers.md |
| Updating rules or instruction files | <rules-path>/maintenance.md |
| Deciding whether to invoke a skill | <rules-path>/customize/skill-triggers.md (if installed) |
| Project/team-specific conventions | <rules-path>/customize/ (scan all .md files) |
```

Handle CLAUDE.md and AGENTS.md as two SEPARATE existing-file checks:

- If neither exists: create both with the above content.
- If CLAUDE.md exists but AGENTS.md does not (or vice versa): create the
  missing one; for the existing one, apply the same append/replace/skip
  choice below.
- For each file that already exists, show the user the content that would
  be added and ask whether to:
  - **Append**: add the generated content to the existing file
  - **Replace**: overwrite with the generated content (backup first)
  - **Skip**: leave the file unchanged (warn that the rules themselves still
    auto-load either way — Skip only forgoes the router content for that
    file: the dispatch-discipline reminder, the cross-tool interface, and
    the PRIMARY-roles declaration)

### Step 9: Detect agent collisions

Scan `<target>/agents/` for all agent definitions (not just tlor-orchestration).
If agents from OTHER sources are found with overlapping functionality:

Report collisions:

| Agent | Source | Overlaps with |
|-------|--------|---------------|
| (name) | (plugin/source) | (tlor-orchestration role) |

The AGENTS.md routing table already declares tlor-orchestration as PRIMARY targets.
Remind the user that explicit routing in AGENTS.md is the only reliable way
to prevent namespace-based agent selection in multi-plugin environments.

### Step 10: Offer hooks (opt-in)

Present available hooks with clear descriptions:

1. **institution_guard** (PreToolUse): Blocks the main session from directly
   editing rules/CLAUDE.md/AGENTS.md files. Enforces "commander doesn't do
   field work" — edits must go through subagent dispatch. Subagents are
   always allowed through.
   - Activated by setting `TLOR_INSTITUTION_GUARD=1` in your environment
   - Python-first, bash fallback if Python 3 unavailable

2. **verify_gate** (Stop): Blocks turn completion when code files were edited
   but no test command was detected. Enforces fail-then-pass evidence.
   - Activated by setting `TLOR_VERIFY_GATE=1` in your environment
   - Requires Python 3

3. **dispatch_guard** (PreToolUse): Denies Agent dispatches with
   `subagent_type: general-purpose` or `claude` unless the prompt contains the
   literal marker `[bombadil-freeagent]` AND an explicit `model` parameter is passed.
   Redirects naming slips to the pinned roles (dispatch.md §3).
   - Activated by setting `TLOR_DISPATCH_GUARD=1` in your environment
   - Requires Python 3

Let the user choose per-hook: install or skip. Do NOT install any hook without
explicit consent.

For hooks chosen: copy `hooks/institution_guard.py`, `hooks/institution_guard.sh`
(bash fallback used when Python 3 is unavailable), `hooks/pre_tool_use.sh`
(dispatcher entry point), `hooks/verify_gate.py`, and `hooks/dispatch_guard.py`
from the plugin bundle
to `~/.claude/institution/hooks/` (this lands at
`~/.claude/hooks/` through the Step 3 symlink). Then explain that activation
is still via environment variables. Tell the user to add the relevant env
var to their shell profile:

```bash
# Add to ~/.zshrc or ~/.bashrc
export TLOR_INSTITUTION_GUARD=1  # Enable institution file guard
export TLOR_VERIFY_GATE=1        # Enable test verification gate
```

### Step 11: Install workflow scripts

Workflow scripts are plugin-owned, code-enforced STDD phases (currently
`workflows/stdd-execute.js`) — copy them from the plugin's `workflows/`
directory to `<target>/workflows/` as an **unconditional overwrite**, the
same treatment Step 4 gives base rules (no frontmatter to preserve, so
nothing user-writable is at risk). The same treatment applies to the
custody-check script the workflow relays to at runtime
(`scripts/stdd_custody_check.py`, REQ-07/REQ-10) — copy it from the plugin's
`scripts/` directory to `<target>/scripts/` as an unconditional overwrite;
the other files under `scripts/` (`check_links.py`, `check_oldname.py`,
`lint_agents_frontmatter.py`) are this repo's own CI tooling, not runtime
dependencies, and are NOT installed.

Destination by install level:

- **User level**: `~/.claude/workflows/`, `~/.claude/scripts/`
- **Project level**: `.claude/workflows/`, `.claude/scripts/`
- **Repo level**: `<user-specified path>/workflows/`, `<user-specified path>/scripts/`

`install.sh` is the single source of truth for the actual copy/manifest
mechanics (mirrors its hooks-copy loop, with its own `.tlor-manifest` at
each destination) — run `./install.sh --dry-run` to preview what it will do
for the current installation before applying it for real.

### Step 12: Report summary

Print installation summary:

```
tlor-orchestration initialization complete:
  Agents:    N installed (M updated-with-backup, K unchanged)
  Rules:     N installed (M updated, K skipped)
  Optional:  N installed (rules/customize/)
  STDD:      role=RD/PM/UIUX/ALL/skip (N skills installed)
  CLAUDE.md: created / updated / skipped
  AGENTS.md: created / updated / skipped
  Hooks:     institution_guard (enabled/skipped), verify_gate (enabled/skipped)
  Workflows: N installed (workflows/)
  Scripts:   N installed (scripts/)
  Backups:   N file(s) as <file>.bak-YYYYMMDD-HHMMSS (see per-file list above)
```

## Notes

- This skill is idempotent — safe to run multiple times
- There is no separate backup directory — agent file backups are per-file
  `<file>.bak-YYYYMMDD-HHMMSS` siblings next to the live file itself (Step
  3); the timestamp means re-running the same day never overwrites an
  earlier backup
- Use `/tlor-restore` to rollback from a backup
- All files use semantic versioning (X.Y.Z) in frontmatter for upgrade detection
- Agent role files never lose local customization silently: a differing
  file is always backed up to `<file>.bak-YYYYMMDD-HHMMSS` before being
  overwritten (Step 3) — `install.sh` is the source of truth for this
  behavior, and `/tlor-init` matches it exactly, no interactive merge
  involved. Base rule files remain plugin-owned and are always overwritten
  unconditionally, with no backup (Step 4); this asymmetry is intentional,
  not an oversight.
