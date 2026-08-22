# Maintenance

[← Back to README](../../README.md)

## Notes

- **CLAUDE.md + AGENTS.md architecture.** `/tlor-init` generates a thin
  `CLAUDE.md` (with an `@AGENTS.md` import) plus an `AGENTS.md` carrying the
  routing table. AGENTS.md is also readable by other AI coding tools
  (Cursor, Codex, etc.), so the routing table isn't locked to Claude Code.
  CLAUDE.md holds no monopoly on auto-loading, though: in Claude Code, files
  under `.claude/rules/` load the same way, and each one carries a real
  per-session cost. [installation.md](installation.md)'s Session-start cost
  section has the measured figures.
- **Serena tools are optional.** The two search roles list
  [Serena](https://github.com/oraios/serena) semantic tools in `tools`.
  Without the plugin they fall back to Grep/Glob, as their instructions say.
- **Hard rules slot**: `eagle-sentinel` treats caller-supplied "Hard Rules"
  (non-negotiable house conventions pasted into its prompt) as auto-FAIL on
  violation. Paste yours when dispatching.
- Model names (`haiku`/`sonnet`/`opus`) follow the Agent tool's accepted
  values; edit the frontmatter if your environment differs. The rules
  themselves speak in tiers (cheap/mid-tier/top-tier), which keeps them
  portable while the agent frontmatter names specific models.

## Limits (honest notes)

- **"Read-only" is behavioral for Bash-carrying roles.** `eagle-sentinel`,
  `elf-archer`, `orc-saboteur`, `rohirrim-outrider` and `ranger-pathfinder` hold Bash to run tests/inspection; Bash can
  technically write, so their never-edits stance is an instruction, not a sandbox.
  `hobbit-gardener` is the one panel role that is read-only at the tool level.
- **Unavailable model → silent fallback.** Per official docs, a `model:` value
  your org excludes makes the subagent run on the inherited session model
  instead, and nothing reports the substitution. With no opus access,
  `eagle-sentinel` quietly runs on whatever your session is using.
- **Security-lens roles may trip a model's safety filter.** `orc-saboteur`
  (and to a lesser degree `elf-archer`) do adversarial *defensive* review; on
  some models a broad safety classifier may read that as offensive-security
  work and auto-switch models mid-task. It's a known false positive, and the
  review still completes. We keep the wording defensive to make it rarer.

## Releasing (maintainers)

Before publishing changes, run `claude plugin validate . --strict` (it
validates plugin.json plus the agent frontmatter), test locally with
`claude --plugin-dir .`, then bump `version` in `.claude-plugin/plugin.json`.
Users receive an update only when that version changes.

Full version-by-version history: [release_log.md](../release_log.md). Append
future releases there.
