---
name: tlor-restore
description: 'Restore-from-backup ritual — rolls back the tlor-orchestration installation to a backup created by `/tlor-init` or `install.sh`. Run explicitly via `/tlor-restore`.'
disable-model-invocation: true
---

# /tlor-restore — Rollback to Previous Installation

Restore files from a backup created by `/tlor-init` or `install.sh`.

## Workflow

### Step 1: Find backups

Backups are per-file siblings named `<file>.bak-YYYYMMDD-HHMMSS`, created
next to the live file whenever `/tlor-init` or `install.sh` overwrites an
agent role file that differs from the bundled copy (Step 3 of `/tlor-init`;
the agent-role loop in `install.sh`). Search for them at all standard
locations:

```bash
# Check for per-file backups (current format)
for base in ~/.claude/agents .claude/agents agents; do
  ls -1 "$base"/*.bak-[0-9]*-[0-9]* 2>/dev/null
done
```

**Legacy fallback** — machines that ran an older version of this installer
may instead have whole-directory backups from before the per-file scheme
existed. Check for those too, and label them explicitly as legacy if found:

```bash
# Legacy format: .tlor-backup-YYYYMMDD/ directories
for base in ~/.claude .claude .; do
  ls -d "$base"/.tlor-backup-* 2>/dev/null
done
```

If neither format is found: report "No backups found. Backups are created
automatically when `/tlor-init` or `install.sh` overwrites a differing
agent file. Run `/tlor-init` or `./install.sh` to create a fresh
installation." and stop.

### Step 2: List available backups

**Per-file backups** (current format) — present sorted by timestamp
(newest first), grouped by original file:

| Original file | Backup | Timestamp | Size |
|------|--------|-----------|------|
| (path, no .bak suffix) | (path).bak-YYYYMMDD-HHMMSS | YYYY-MM-DD HH:MM:SS | X KB |

**Legacy directory backups**, if any were found — present separately and
labeled `[legacy]`:

| Backup | Date | Files | Size |
|--------|------|-------|------|
| [legacy] .tlor-backup-YYYYMMDD | YYYY-MM-DD | N files | X KB |

Let the user choose which backup(s) to restore — for per-file backups this
can be a single file or "all backups from this run" (same timestamp);
for a legacy directory it is the whole directory as one unit.

### Step 3: Preview restoration

Show what will be restored:

| File | Current version | Backup version | Action |
|------|----------------|----------------|--------|
| (path) | (current ver or "missing") | (backup ver) | restore / skip |

Ask the user to confirm: "Restore N file(s) from the selected backup(s)?
This will overwrite the current installation. [Confirm / Cancel]"

### Step 4: Execute restoration

**Per-file backups**: for each selected `<file>.bak-YYYYMMDD-HHMMSS`, copy
it over the live `<file>` (stripping the `.bak-...` suffix), then verify
the copy (file exists, size matches).

**Legacy directory backups**: for each file inside the selected
`.tlor-backup-YYYYMMDD/` directory, copy it to the corresponding original
installation path, then verify the copy (file exists, size matches).

Do NOT delete the backup after restoring — it remains available for future use.

### Step 5: Report

```
tlor-orchestration restore complete:
  Source:    <file>.bak-YYYYMMDD-HHMMSS (or [legacy] .tlor-backup-YYYYMMDD/)
  Restored:  N files
  Skipped:   M files
  Backup preserved (not deleted)
```

Suggest running `/tlor-init` afterwards to check if further updates are
available.

## Notes

- Backups are created by `/tlor-init` or `install.sh` whenever an agent
  file differs from the bundled copy at install/upgrade time — one
  `<file>.bak-YYYYMMDD-HHMMSS` sibling per overwritten file, not a single
  directory snapshot
- The timestamp (not just the date) means multiple backups from the same
  day are distinct files — none of them get clobbered by a same-day re-run
- Multiple backup points can coexist (different timestamps) per file
- Restoring does NOT delete the backup — you can restore the same backup again
- **Legacy**: `.tlor-backup-YYYYMMDD/` whole-directory backups are a
  fallback for installations made before the per-file scheme existed;
  nothing on the current install/upgrade path creates new ones. If a
  legacy directory backup contains files that no longer exist in the
  current installation, they are recreated at their original paths
