# Installation & ownership

[← Back to README](../../README.md)

## Two ways to use this

- **Lightweight** — just install the plugin. The thirteen roles become available
  in any NEW session after install (in an already-running session, run
  `/reload-plugins` first). Invoke them explicitly by name, or add the
  CLAUDE.md snippet in [roles.md](roles.md) for consistent dispatch — in
  our headless probes, descriptions alone did not reliably trigger automatic
  delegation, so the snippet is the recommended lightweight setup.
- **Full** — additionally run `/tlor-init`. This lays down the rules files,
  the `~/.claude/institution/` layout (see below), and CLAUDE.md/AGENTS.md
  routing. The rules load on their own once present — `.claude/rules/` is a
  native auto-load location, no routing required — while the routing adds a
  dispatch-discipline reminder up front, an AGENTS.md interface for tools
  that don't read `.claude/rules/`, and the declaration that this
  framework's roles are your primary dispatch targets.

## Ownership model

- **Base rules are plugin-owned.** Every install/upgrade overwrites the
  required rule files unconditionally and stamps them with the plugin's
  `version` (the single source of truth — not a value baked into the shipped
  file). Don't hand-edit these; edits are lost on the next install.
- **Agent role files use backup-and-overwrite, never a silent clobber.**
  Agent frontmatter has no import mechanism, so a local edit (e.g. extending
  a role's `tools:` line to add an MCP server) lives only in the installed
  file. Both `/tlor-init` and `install.sh` apply the same rule per file:
  missing → install it; identical to the bundled copy (`cmp -s`) → leave it
  alone; different (whether a hand-edit or an old version) → back it up to
  `<file>.bak-YYYYMMDD-HHMMSS` next to itself, then overwrite it with the
  bundled copy. The timestamp (not just the date) means re-running install
  twice on the same day never clobbers the earlier backup. There is no
  pristine merge-base copy and no interactive Overwrite/Keep/Merge prompt —
  the `.bak-YYYYMMDD-HHMMSS` file is the user's source for re-applying any
  customization by hand afterward.
- **`rules/customize/` is yours.** The installer creates it, may seed it with
  optional starter files on first install, and never overwrites anything
  already there afterward — this is the only place persistent local
  customization belongs.
- **Base files have zero user-writable sections.** All user additions —
  lessons, the skill-namespace-priority table, local patterns — live in
  `rules/customize/`, never in a base rule file, since anything appended
  there is wiped on the next unconditional overwrite.
- **`~/.claude/institution/` layout.** For user-level installs,
  `~/.claude/{agents,rules,hooks}` become symlinks into
  `~/.claude/institution/<name>/`. This is idempotent: already a symlink →
  left alone; a real directory already there → moved under `institution/`
  and symlinked (nothing is lost); missing → created fresh. The indirection
  means the plugin's overwrite-on-install semantics for base rules/hooks
  never fight with a directory you relocated or are backing up by hand.

## Session-start cost

Once installed, the rules corpus is not something routing controls — most of
it loads **in full at the start of every session**. `~/.claude/rules/` (and
its `customize/` subdirectory) is a native Claude Code auto-load location:
every `.md` file under it without `paths:` frontmatter enters context at
launch, recursively, with no `@import` needed. A rule file that carries
`paths:` frontmatter is the documented way to defer it — it loads only when
Claude reads a file matching that pattern, instead of at every session start.

Measured against this shipped repo with `wc -l -c` (self-measure command
below — re-run it yourself, these are one snapshot, not a promise):

```
$ wc -l -c rules/*.md
     795   44155 total
$ wc -l -c rules/customize/*.md
     350   15795 total
$ cat rules/*.md rules/customize/*.md | wc -l -c
    1145   59950
```

So: the six base rule files run **795 lines / ~44.2 KB**, the seeded
`rules/customize/` starter files run **350 lines / ~15.8 KB**, and the
combined per-session floor is **1,145 lines / ~60.0 KB** — before you add a
single lesson of your own. This is a fixed tax paid every session,
regardless of whether that session ever dispatches a subagent. The base
figure applies to every install; the combined figure only holds if you also
took the optional `rules/customize/` seeds (`install.sh --with-optional`) —
a base-only install pays just the base figure.

Two caveats on this mechanism. **Version floor**: `.claude/rules/` auto-load
requires Claude Code 2.0.64 or newer — on an older version the directory is
not read at all, so "routing not required" would leave you with zero rules
loaded, not the lightweight fallback you'd expect. **It can be turned off**:
loading is suppressed by `claudeMdExcludes` in any settings layer, and — for
project-scope rules only — rules are also skipped when project settings are
excluded from `--setting-sources`; don't assume this corpus is unconditional.

This cost hits models with smaller context windows proportionally harder —
and those are exactly this framework's target readers (the whole premise of
dispatch is offloading field work from a constrained context). Weigh this
against the lightweight, plugin-only path above if a per-session budget
matters to you.

## Install

### Option A — as a plugin (recommended)

```
/plugin marketplace add twjohnwu/tlor-orchestration
/plugin install tlor@tlor
```

Updates: bump happens on our side via the `version` field; refresh with
`/plugin marketplace update tlor`.

### Updates

Update support requires the marketplace installation route (Option A):
`/plugin marketplace add twjohnwu/tlor-orchestration` then
`/plugin install tlor@tlor`. Every release bumps
`.claude-plugin/plugin.json`'s `version` — per Claude Code's plugin docs,
pushing commits alone does not surface an update; only a version bump does,
and `/plugin marketplace update tlor` then pulls it. The `install.sh` plain-
copy route (Option B) has no update UI at all — re-running `install.sh`
overwrites base rules again, but there's no notification that a new version
exists; check the repo's releases/version badge yourself.

### Option B — plain copy

```bash
git clone https://github.com/twjohnwu/tlor-orchestration.git
cd tlor-orchestration && ./install.sh          # --dry-run / --force / --uninstall / --with-optional / --stdd-role=ALL / --install-hook / --skills-dest=PATH
```

Copies agents to `~/.claude/agents/`, rules to `~/.claude/rules/`, hook
scripts to `~/.claude/hooks/`, and skills to `~/.claude/skills/`, setting up
the `~/.claude/institution/` symlink layout on first run (see Ownership
model above). Add `--with-optional` to include the optional rules installed
from `rules/customize/`. Records manifests for clean `--uninstall`. Hook
*activation* (env vars, `hooks.json` wiring) still needs the plugin route
(Option A) — `install.sh` only places the files.

**`--stdd-role=RD|PM|UIUX|ALL`** — opt-in install of the STDD workflow
skills (`stdd-skills/*`, non-autoload; see [skills.md](skills.md)). Only
`ALL` is implemented this round; `RD`/`PM`/`UIUX` print a deferred message
and install nothing. No flag → no STDD skills, unchanged from before this
flag existed.

**`--install-hook`** — opt-in install + `settings.json` registration of the
STDD test-file guard (`hooks/stdd_test_guard.py`). Default NOT installed.
**Honest caveat**: Claude Code reads PreToolUse hooks from `settings.json`
once, at session start — a resumed/continued session will NOT pick up a
hook registered mid-session. Verify this hook in a brand-new (non-resumed)
session only.

**`--skills-dest=PATH`** — declare the skills install directory once. `PATH`
must be an absolute path, and not `$HOME` or `/` itself. The declaration
persists to `~/.claude/.tlor-install.conf` (a plain `skills_dest=PATH` line,
read with `grep`/`cut`, never sourced), so a later run with no flag still
installs to the same place. Without a declaration (no flag, no config line),
a `~/.claude/skills` symlink resolving outside `~/.claude` still aborts the
whole install — that safety default is deliberate and unchanged; an explicit
`--skills-dest` declaration is how you opt out of it for a skills directory
you keep elsewhere on purpose.

**Lightweight users** (plugin only, no `/tlor-init`): see the CLAUDE.md
snippet in [roles.md](roles.md) to get dispatch discipline without the full
rules install.

### Option C — /tlor-init (recommended after plugin install)

After installing via Option A, run `/tlor-init` in Claude Code for guided
setup: choose installation level, install rules, generate CLAUDE.md and
AGENTS.md routing, and optionally enable hooks.

Either way, **open a new Claude Code session afterwards** — agent definitions
are loaded at session start.
