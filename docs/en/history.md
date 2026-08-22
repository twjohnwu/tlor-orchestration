# History

[← Back to README](../../README.md)

## Renamed: tlor-agents → tlor-orchestration (2.x → 3.0)

This repo was renamed from `tlor-agents` to `tlor-orchestration`. GitHub
redirects the old URLs automatically, but plugin installs are keyed by repo
name, so you have to redo the install by hand:

```
/plugin uninstall tlor-agents@tlor        # remove the old install
/plugin marketplace add twjohnwu/tlor-orchestration
/plugin install tlor@tlor   # re-add under the new name
```

If you installed via `install.sh` (plain copy), re-run the new `install.sh`
instead; the ownership model in [installation.md](installation.md) says what
changes on upgrade.

v3.0.0 also changes that ownership model (again, see
[installation.md](installation.md)): base rule files are now plugin-owned
and overwritten unconditionally on every install, so anything you want to
keep across upgrades belongs in `rules/customize/`, which the installer
never touches. If you hand-edited a base rule file in place under 2.x, move
those edits into `rules/customize/` before upgrading; otherwise the next
install replaces that file with the shipped version.

## Versioning reset (3.0.0 → 0.0.1)

The project has been through three architecture stages: (1) agents role
base (1.x — nine pinned role definitions), (2) rule-assigned agents (2.x–3.0
— roles wired to institution dispatch rules), (3) orchestration (0.x — a
full orchestration framework, with process pipelines such as STDD still to
be integrated). That repositioning is what restarts versioning at 0.0.1.

Machines with 2.x/3.x installed will NOT pick up the lower version via
`/plugin marketplace update`, since Claude Code's plugin version resolution
ignores downgrades. To migrate: uninstall the plugin, remove the
marketplace, re-add the marketplace, then reinstall.

For the full version-by-version log (including everything before and after
this repositioning), see [release_log.md](../release_log.md).
