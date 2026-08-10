#!/usr/bin/env bash
# install.sh — copy TLOR agent roles, skills, rules, hooks, workflows, and
# scripts into ~/.claude/
# (no plugin system needed).
# Usage: ./install.sh [--dry-run] [--force] [--uninstall] [--with-optional]
#                      [--stdd-role=RD|PM|UIUX|ALL] [--install-hook]
#                      [--skills-dest=PATH]
# Prefer the plugin route when possible:
#   /plugin marketplace add twjohnwu/tlor-orchestration   then   /plugin install tlor@tlor
#
# --stdd-role=RD|PM|UIUX|ALL: opt-in install of the STDD workflow skills
#   (stdd-skills/*, non-autoload). Only ALL is implemented this round; RD/PM/
#   UIUX print a deferred message and install nothing (see
#   specs/stdd-integration.md S-33/S-35). No flag => no STDD skills, same as
#   before this flag existed.
# --install-hook: opt-in install + settings.json registration of the STDD
#   test-file guard (REQ-09). Default NOT installed. HONEST CAVEAT: Claude
#   Code reads PreToolUse hooks from settings.json once, at session start —
#   a resumed/continued session will NOT pick up a hook registered mid-
#   session. Verify this hook in a brand-new (non-resumed) session only.
# --skills-dest=PATH: declare the skills install directory once, persisted
#   to ~/.claude/.tlor-install.conf so later runs need no flag. Must be an
#   absolute path, and not $HOME or /. Without a declaration, a
#   ~/.claude/skills symlink resolving outside ~/.claude still aborts the
#   whole install (deliberate — see ensure_skills_dest_safe below).
set -euo pipefail

: "${HOME:?HOME is not set — refusing to guess an install location}"
ROOT="$(cd "$(dirname "$0")" && pwd)"
SRC="$ROOT/agents"
SKILLS_SRC="$ROOT/skills"
RULES_SRC="$ROOT/rules"
HOOKS_SRC="$ROOT/hooks"
WORKFLOWS_SRC="$ROOT/workflows"
SCRIPTS_SRC="$ROOT/scripts"
STDD_SKILLS_SRC="$ROOT/stdd-skills"
PLUGIN_JSON="$ROOT/.claude-plugin/plugin.json"

INSTITUTION="$HOME/.claude/institution"
DEST="$HOME/.claude/agents"
RULES_DEST="$HOME/.claude/rules"
HOOKS_DEST="$HOME/.claude/hooks"
WORKFLOWS_DEST="$HOME/.claude/workflows"
SCRIPTS_DEST="$HOME/.claude/scripts"
SETTINGS_JSON="$HOME/.claude/settings.json"
INSTALL_CONF="$HOME/.claude/.tlor-install.conf"
MANIFEST="$DEST/.tlor-manifest"
RULES_MANIFEST="$RULES_DEST/.tlor-manifest"
HOOKS_MANIFEST="$HOOKS_DEST/.tlor-manifest"
WORKFLOWS_MANIFEST="$WORKFLOWS_DEST/.tlor-manifest"
SCRIPTS_MANIFEST="$SCRIPTS_DEST/.tlor-manifest"

DRY=0; FORCE=0; UNINSTALL=0; WITH_OPTIONAL=0; STDD_ROLE=""; INSTALL_HOOK=0; SKILLS_DEST_ARG=""
for a in "$@"; do
  case "$a" in
    --dry-run) DRY=1;;
    --force) FORCE=1;;
    --uninstall) UNINSTALL=1;;
    --with-optional) WITH_OPTIONAL=1;;
    --stdd-role=*) STDD_ROLE="${a#*=}";;
    --install-hook) INSTALL_HOOK=1;;
    --skills-dest=*) SKILLS_DEST_ARG="${a#*=}";;
    *) echo "unknown arg: $a" >&2; exit 1;;
  esac
done

case "$STDD_ROLE" in
  ""|RD|PM|UIUX|ALL) ;;
  *) echo "unknown --stdd-role value: $STDD_ROLE (expected RD|PM|UIUX|ALL)" >&2; exit 1;;
esac

# Resolve the skills destination: CLI flag > config file > default. The
# config file (a plain `key=value` line list) is read with grep/cut, never
# `source`d — it must not be able to execute arbitrary content.
# SKILLS_DEST_SOURCE tracks where the value came from ("flag"/"config"/
# "default") so ensure_skills_dest_safe below knows whether the destination
# was explicitly declared (skip the symlink-outside-~/.claude abort) or is
# still the undeclared default (keep the abort exactly as before).
SKILLS_DEST_SOURCE="default"
SKILLS_DEST_CONFIG=""
if [ -f "$INSTALL_CONF" ]; then
  SKILLS_DEST_CONFIG="$(grep -m1 '^skills_dest=' "$INSTALL_CONF" 2>/dev/null | cut -d= -f2-)"
fi
if [ -n "$SKILLS_DEST_ARG" ]; then
  SKILLS_DEST="$SKILLS_DEST_ARG"
  SKILLS_DEST_SOURCE="flag"
elif [ -n "$SKILLS_DEST_CONFIG" ]; then
  SKILLS_DEST="$SKILLS_DEST_CONFIG"
  SKILLS_DEST_SOURCE="config"
else
  SKILLS_DEST="$HOME/.claude/skills"
fi

if [ "$SKILLS_DEST_SOURCE" != "default" ]; then
  case "$SKILLS_DEST" in
    /*) ;;
    *) echo "--skills-dest must be an absolute path, got: $SKILLS_DEST" >&2; exit 1;;
  esac
  if [ "$SKILLS_DEST" = "$HOME" ] || [ "$SKILLS_DEST" = "/" ]; then
    echo "--skills-dest must not be \$HOME or / itself, got: $SKILLS_DEST" >&2
    exit 1
  fi
fi

if [ "$SKILLS_DEST_SOURCE" = "flag" ] && [ "$DRY" -ne 1 ]; then
  # Persist the declared destination so a later run with no flag still finds
  # it — create the conf file if absent, replace an existing skills_dest=
  # line rather than appending a duplicate, and preserve any other keys.
  mkdir -p "$HOME/.claude"
  if [ -f "$INSTALL_CONF" ] && grep -q '^skills_dest=' "$INSTALL_CONF"; then
    sed -i.bak-tlor "s|^skills_dest=.*|skills_dest=$SKILLS_DEST|" "$INSTALL_CONF"
    rm -f "$INSTALL_CONF.bak-tlor"
  else
    printf 'skills_dest=%s\n' "$SKILLS_DEST" >> "$INSTALL_CONF"
  fi
fi

SKILLS_MANIFEST="$SKILLS_DEST/.tlor-manifest"
STDD_MANIFEST="$SKILLS_DEST/.tlor-stdd-manifest"

# S-33 profile table (config-driven, per specs/stdd-integration.md S-33):
# maps a 視角 to its STDD skill dir subset. RD/PM/UIUX subsets are recorded
# here for a future implementation session but are NOT installed this round
# (deferred, D5) — `install.sh` currently only implements ALL, and prints a
# deferred message for RD/PM/UIUX instead of installing their subset. ALL's
# list is discovered dynamically from stdd-skills/*/ rather than hardcoded,
# so a future 8th skill needs no change here.
#
# NOTE for a future RD/PM/UIUX implementation: stdd-explore, stdd-uiux, and
# stdd-plan reference shared files under stdd-spec/references/* — none of
# the three profile subsets above include stdd-spec itself. Whoever
# implements RD/PM/UIUX must either also install stdd-spec alongside the
# listed skills, or relocate the shared references somewhere all profiles
# can reach without depending on a skill outside their own subset.
stdd_profile_skills() {
  case "$1" in
    RD)   echo "stdd-plan stdd-execute stdd stdd-lint" ;;
    PM)   echo "stdd-explore stdd-spec stdd stdd-lint" ;;
    UIUX) echo "stdd-explore stdd-uiux stdd stdd-lint" ;;
    ALL)  (cd "$STDD_SKILLS_SRC" && ls -d */ | sed 's|/$||') ;;
    *)    echo "" ;;
  esac
}

# Single source of truth for the version stamped into every base rule file's
# frontmatter — read directly from plugin.json, no jq dependency.
VERSION=$(grep -m1 '"version"' "$PLUGIN_JSON" | sed -E 's/.*"version": *"([^"]+)".*/\1/')

ROLES=$(cd "$SRC" && ls ./*.md | sed 's|^\./||')
SKILLS=$(cd "$SKILLS_SRC" && ls -d */ | sed 's|/$||')
RULES=$(cd "$RULES_SRC" && ls ./*.md | sed 's|^\./||')
HOOK_FILES="institution_guard.py institution_guard.sh pre_tool_use.sh verify_gate.py dispatch_guard.py"
WORKFLOWS=$(cd "$WORKFLOWS_SRC" && ls ./*.js | sed 's|^\./||')
# Only the runtime dependency (the custody-check script `workflows/stdd-execute.js`
# relays to at runtime, REQ-07/REQ-10) is installed — the rest of scripts/
# (check_links.py, check_oldname.py, lint_agents_frontmatter.py) is this
# repo's own CI tooling, not something an installed plugin needs.
SCRIPTS="stdd_custody_check.py"
CUSTOMIZE_SRC="$RULES_SRC/customize"
CUSTOMIZE_FILES=""
if [ "$WITH_OPTIONAL" -eq 1 ]; then
  CUSTOMIZE_FILES=$(cd "$CUSTOMIZE_SRC" && ls ./*.md 2>/dev/null | sed 's|^\./||')
fi

# Idempotent institution layout: ~/.claude/{agents,rules,hooks} become
# symlinks into ~/.claude/institution/<name>, so this plugin's overwrite-on-
# install semantics for base rules/hooks never clobber a directory the user
# relocated or is backing up by hand. Three branches per path:
#   already a symlink        -> skip
#   a real directory exists  -> move it under institution/<name>, then symlink
#   missing                  -> create institution/<name>, then symlink
# Resolve a directory symlink to its real target, portably (no GNU
# readlink -f on macOS). This is only ever called on directory symlinks
# (agents/rules/hooks/skills dest dirs), so the pure-shell `cd -P && pwd -P`
# idiom is sufficient — no python3 dependency needed.
resolve_symlink() {
  local target="$1"
  (cd -P "$target" 2>/dev/null && pwd -P) || true
}

ensure_institution_symlink() {
  local name="$1"
  local target="$HOME/.claude/$name"
  local real="$INSTITUTION/$name"
  if [ -L "$target" ]; then
    # Existing symlinks get written through by later install steps (agents/
    # rules/hooks land at $target/<file>), so a symlink pointing somewhere
    # outside the institution tree must abort rather than silently write
    # into an unrelated location.
    local resolved
    resolved="$(resolve_symlink "$target")"
    case "$resolved" in
      "$INSTITUTION"/*)
        echo "institution: $target already a symlink -> $resolved — skip"
        ;;
      *)
        echo "ABORT: $target is a symlink pointing outside $INSTITUTION (resolved: ${resolved:-<unresolved>}) — refusing to write through it." >&2
        exit 1
        ;;
    esac
  elif [ -e "$target" ]; then
    if [ "$DRY" -eq 1 ]; then
      echo "would move $target -> $real and symlink"
    else
      mkdir -p "$INSTITUTION"
      mv "$target" "$real"
      ln -s "$real" "$target"
      echo "institution: moved $target -> $real, symlinked"
    fi
  else
    if [ "$DRY" -eq 1 ]; then
      echo "would create $real and symlink $target"
    else
      mkdir -p "$real"
      ln -s "$real" "$target"
      echo "institution: created $real, symlinked $target"
    fi
  fi
}

# Skills are NOT part of the institution tree (agents/rules/hooks) — they
# stay a plain directory at ~/.claude/skills by design. But if the user (or
# some other tool) turned it into a symlink, the constraint is narrower than
# ensure_institution_symlink's: the target only needs to resolve somewhere
# inside ~/.claude, not specifically under institution/. Anything outside
# aborts rather than silently writing skill files through it.
ensure_skills_dest_safe() {
  if [ "$SKILLS_DEST_SOURCE" != "default" ]; then
    echo "skills dest declared: $SKILLS_DEST (source: $SKILLS_DEST_SOURCE)"
    return
  fi
  local target="$SKILLS_DEST"
  if [ -L "$target" ]; then
    local resolved
    resolved="$(resolve_symlink "$target")"
    case "$resolved" in
      "$HOME/.claude"/*|"$HOME/.claude")
        echo "skills: $target already a symlink -> $resolved — ok"
        ;;
      *)
        echo "ABORT: $target is a symlink pointing outside $HOME/.claude (resolved: ${resolved:-<unresolved>}) — refusing to write through it." >&2
        exit 1
        ;;
    esac
  fi
}

# Build a `<file>.bak-YYYYMMDD-HHMMSS` path for $1, guaranteed not to
# already exist. Second-granularity timestamps collide when install.sh runs
# twice within the same second (e.g. scripted back-to-back runs) — on
# collision, append `-2`, `-3`, ... until the path is free, so an earlier
# backup from the same second is never silently overwritten.
unique_backup_path() {
  local file="$1"
  local stamp base n
  stamp="$(date +%Y%m%d-%H%M%S)"
  base="$file.bak-$stamp"
  if [ ! -e "$base" ]; then
    echo "$base"
    return
  fi
  n=2
  while [ -e "$base-$n" ]; do
    n=$((n+1))
  done
  echo "$base-$n"
}

# Inject `version: X.Y.Z` (from plugin.json) into a rule file's frontmatter —
# replaces an existing `version:` line if present, otherwise inserts one
# before the closing `---`. This is the only place a base rule file's
# version comes from; the shipped file itself is not authoritative.
inject_version() {
  local file="$1"
  awk -v ver="$VERSION" '
    NR==1 && $0=="---" { print; infm=1; next }
    infm && /^version:/ { print "version: " ver; done=1; next }
    infm && $0=="---" { if (!done) print "version: " ver; print; infm=0; next }
    { print }
  ' "$file" > "$file.tmp.$$" && mv "$file.tmp.$$" "$file"
}

if [ "$UNINSTALL" -eq 1 ]; then
  # Per-asset-type uninstall policy (REQ-10/S-15) — the eight loops below
  # (agents, skills, rules, hooks, workflows, scripts, STDD skills, the
  # stdd_test_guard hook) intentionally do NOT all behave the same way; this
  # is a stated decision, not accidental drift:
  #   agents            -> .bak backup of customized files, then `rm` (this
  #                        is the only asset type the user commonly hand-
  #                        edits per-role, so a silent hand-edit loss would
  #                        be the most costly of the eight)
  #   skills            -> `rm -rf`, no backup (skill dirs are bundled
  #                        wholesale from this checkout; users are not
  #                        expected to hand-edit inside $SKILLS_DEST)
  #   rules             -> `rm`, no backup, plus an `rmdir` of the now-empty
  #                        `customize/` dir (rules/customize/ is the user's
  #                        own content by convention — see rules/customize/*
  #                        — so it is never touched by the remove loop itself;
  #                        the rmdir only clears the directory shell it leaves
  #                        behind, never a file in it)
  #   hooks             -> `rm`, no backup (plugin-owned scripts, unconditional
  #                        overwrite already documented at install time near
  #                        `HOOK_FILES`; nothing here is meant to be hand-edited)
  #   workflows         -> `rm`, no backup (plugin-owned, code-enforced STDD
  #                        phase scripts; same unconditional-overwrite
  #                        treatment as hooks — nothing here is meant to be
  #                        hand-edited)
  #   scripts           -> `rm`, no backup (same rationale as workflows — the
  #                        one file installed, `stdd_custody_check.py`, is a
  #                        plugin-owned runtime dependency of workflows/
  #                        stdd-execute.js, not user-editable content)
  #   STDD skills       -> `rm -rf`, no backup, but scoped strictly to what
  #                        our own $STDD_MANIFEST recorded (never a guessed
  #                        subset) — same "bundled, not hand-edited" rationale
  #                        as skills, with an extra custody constraint because
  #                        this is an opt-in install
  #   stdd_test_guard.py -> `rm`, no backup; its settings.json registration is
  #                        deliberately left in place (rewriting someone else's
  #                        settings.json unprompted is a T2 action this script
  #                        does not take — see the loop's own comment below)
  # In short: `.bak` is reserved for the one asset type (agents) where a
  # customization surviving uninstall actually matters to the user; the rest
  # are treated as disposable, re-installable bundle content.
  #
  # Manifest entries name a single path component under a known dest dir
  # (a filename or a skill-dir name) — never a nested path. Reject anything
  # empty, anything that could escape the dest dir via `/` or `..`, and
  # anything containing glob metacharacters (`*` `?` `[`) or whitespace —
  # a manifest line is read with quoting discipline below, but a stray glob
  # character in an entry could still surprise a caller that globs on it
  # elsewhere, so reject it at the source rather than trusting call sites.
  is_safe_manifest_entry() {
    local e="$1"
    if [ -z "$e" ]; then return 1; fi
    case "$e" in
      */*|*..*|*'*'*|*'?'*|*'['*|*' '*|*"$(printf '\t')"*|*"$(printf '\r')"*) return 1 ;;
    esac
    return 0
  }

  # Remove what was actually installed (manifest), not what the current
  # checkout happens to contain; fall back to the checkout list if no
  # manifest exists (pre-1.1.0 installs). Manifest lines are read with
  # `while IFS= read -r` directly from the file — never `for x in
  # $(cat ...)` — so a line containing a glob (`*`) or whitespace is never
  # word-split or glob-expanded against the current working directory.
  #
  # uninstall_asset MODE argument encodes the one behavior axis that
  # genuinely differs per asset type (see the policy comment block above):
  #   file_backup -> agents only: .bak-preserve a locally-customized file
  #                  (differs from $SRC's bundled copy) before `rm`
  #   dir_rm      -> skills only: `rm -rf`, no backup
  #   file_plain  -> rules/hooks/workflows/scripts: `rm`, no backup
  # Everything else (manifest-vs-fallback selection, unsafe-entry skip,
  # dry-run echo, final manifest removal) is identical across all six and
  # lives in this one function — a 7th plain file-type asset costs one call.
  # Parallel-array note: this repo targets macOS's bundled bash 3.2, which
  # has no associative arrays, so each asset is just five positional args to
  # one function rather than a lookup table.
  uninstall_asset() {
    local label="$1" dest="$2" manifest="$3" mode="$4"; shift 4
    local fallback="$*"
    local remove_src
    if [ -f "$manifest" ]; then remove_src="$manifest"; else remove_src=""; fi
    local f bak
    while IFS= read -r f || [ -n "$f" ]; do
      if ! is_safe_manifest_entry "$f"; then
        echo "WARNING: skipping unsafe manifest entry '$f' in ${remove_src:-$manifest (fallback list)}" >&2
        continue
      fi
      case "$mode" in
        file_backup)
          if [ -f "$dest/$f" ]; then
            # Preserve a customized agent file (differs from this checkout's
            # bundled copy) as a .bak before removing it — uninstall should
            # never discard a hand-edit the user never asked to lose.
            if [ -f "$SRC/$f" ] && ! cmp -s "$SRC/$f" "$dest/$f"; then
              bak="$(unique_backup_path "$dest/$f")"
              if [ "$DRY" -eq 1 ]; then
                echo "would preserve customized $dest/$f -> $bak before removing"
              else
                cp "$dest/$f" "$bak"
                echo "preserved customized $dest/$f -> $bak"
              fi
            fi
            [ "$DRY" -eq 1 ] && echo "would remove $dest/$f" || { rm "$dest/$f"; echo "removed $dest/$f"; }
          fi
          ;;
        dir_rm)
          if [ -d "$dest/$f" ]; then
            [ "$DRY" -eq 1 ] && echo "would remove $dest/$f" || { rm -rf "$dest/$f"; echo "removed $dest/$f"; }
          fi
          ;;
        file_plain)
          if [ -f "$dest/$f" ]; then
            [ "$DRY" -eq 1 ] && echo "would remove $dest/$f" || { rm "$dest/$f"; echo "removed $dest/$f"; }
          fi
          ;;
      esac
    done < <(if [ -n "$remove_src" ]; then cat "$remove_src"; else printf '%s\n' $fallback; fi)
    if [ "$label" = "rules" ]; then
      # rules/customize/ is the user's own landing zone (never removed by
      # the loop above) — only the now-empty directory shell is cleared.
      [ -d "$dest/customize" ] && rmdir "$dest/customize" 2>/dev/null || true
    fi
    if [ "$DRY" -eq 0 ] && [ -f "$manifest" ]; then rm "$manifest"; fi
  }

  uninstall_asset agents    "$DEST"           "$MANIFEST"           file_backup $ROLES
  uninstall_asset skills    "$SKILLS_DEST"    "$SKILLS_MANIFEST"    dir_rm      $SKILLS
  uninstall_asset rules     "$RULES_DEST"     "$RULES_MANIFEST"     file_plain  $RULES
  uninstall_asset hooks     "$HOOKS_DEST"     "$HOOKS_MANIFEST"     file_plain  $HOOK_FILES
  uninstall_asset workflows "$WORKFLOWS_DEST" "$WORKFLOWS_MANIFEST" file_plain  $WORKFLOWS
  uninstall_asset scripts   "$SCRIPTS_DEST"   "$SCRIPTS_MANIFEST"   file_plain  $SCRIPTS

  # STDD skills: only remove what our own manifest recorded (never guesses
  # at a subset — the first line is `role=<...>`, the rest are skill dirs).
  if [ -f "$STDD_MANIFEST" ]; then
    while IFS= read -r s || [ -n "$s" ]; do
      if ! is_safe_manifest_entry "$s"; then
        echo "WARNING: skipping unsafe manifest entry '$s' in $STDD_MANIFEST" >&2
        continue
      fi
      if [ -d "$SKILLS_DEST/$s" ]; then
        [ "$DRY" -eq 1 ] && echo "would remove STDD skill $SKILLS_DEST/$s" || { rm -rf "$SKILLS_DEST/$s"; echo "removed STDD skill $SKILLS_DEST/$s"; }
      fi
    done < <(tail -n +2 "$STDD_MANIFEST")
    if [ "$DRY" -eq 0 ]; then rm "$STDD_MANIFEST"; fi
  fi

  # STDD test-file guard hook: remove the copied script AND its settings.json
  # registration. A dangling registration is worse than the T2 cost of
  # editing settings.json: once the script is gone, `python3 <deleted path>`
  # exits 2, which Claude Code reads as a blocking PreToolUse deny — every
  # Edit/Write is refused until hand-fixed. Unregister is attempted
  # UNCONDITIONALLY (not gated on the script still being present) and BEFORE
  # the `rm`, because the exact state this guards against is "script already
  # gone, registration still there" — a gate on the script's existence would
  # skip the fix in precisely that state. register_stdd_hook.py --remove
  # matches any hooks entry that MENTIONS stdd_test_guard.py (not just the
  # exact string this installer wrote), so a hand-edited/differently-quoted
  # entry is still caught, and it exits non-zero only when a matching entry
  # survives unremoved — that's what the WARNING below reports.
  if [ "$DRY" -eq 1 ]; then
    echo "would remove $HOOKS_DEST/stdd_test_guard.py (if present) and unregister its settings.json entry"
  else
    if [ -f "$SETTINGS_JSON" ]; then
      if command -v python3 >/dev/null 2>&1; then
        python3 "$HOOKS_SRC/register_stdd_hook.py" "$SETTINGS_JSON" "$HOOKS_DEST/stdd_test_guard.py" --remove \
          || echo "WARNING: could not fully unregister the stdd_test_guard.py PreToolUse entry — remove it by hand from $SETTINGS_JSON" >&2
      else
        echo "WARNING: python3 not found — could not auto-unregister the hook from $SETTINGS_JSON. Remove it by hand." >&2
      fi
    fi
    if [ -f "$HOOKS_DEST/stdd_test_guard.py" ]; then
      rm "$HOOKS_DEST/stdd_test_guard.py"
      echo "removed $HOOKS_DEST/stdd_test_guard.py"
    fi
  fi

  # Institution layout and its symlinks are left in place on uninstall —
  # unwinding a relocated real directory safely needs a decision only the
  # user can make; use /tlor-restore or undo it by hand.
  if [ "$DRY" -eq 1 ]; then echo "uninstall dry-run done (nothing removed)."; else echo "uninstall done."; fi
  exit 0
fi

for n in agents rules hooks; do
  ensure_institution_symlink "$n"
done
ensure_skills_dest_safe

[ "$DRY" -eq 1 ] || mkdir -p "$DEST"
skill_conflicts=""
for s in $SKILLS; do
  if [ -d "$SKILLS_DEST/$s" ] && ! diff -rq "$SKILLS_SRC/$s" "$SKILLS_DEST/$s" >/dev/null 2>&1; then
    skill_conflicts="$skill_conflicts $s"
  fi
done
if [ -n "$skill_conflicts" ] && [ "$FORCE" -ne 1 ]; then
  echo "ABORT: these skills already exist at $SKILLS_DEST with different content:$skill_conflicts" >&2
  echo "Re-run with --force to overwrite, or remove them first." >&2
  exit 1
fi

# Agent role files: cmp -> backup -> overwrite, not an unconditional
# overwrite. Agent frontmatter has no import mechanism, so a user's hand-edit
# (e.g. extending a role's `tools:` line for an MCP server) lives only in the
# installed file — clobbering it silently would destroy that. No merge base
# is kept: if the live file differs at all from the bundled copy, it is
# backed up to `<file>.bak-YYYYMMDD-HHMMSS` next to itself and then
# overwritten — the timestamp (not just the date) means a same-day re-run
# never clobbers an earlier backup. The .bak is the user's source for
# re-applying any customization by hand.
# This is the default behavior (no --force needed); --force is not used for
# agent files at all.
for f in $ROLES; do
  live="$DEST/$f"
  if [ "$DRY" -eq 1 ]; then
    echo "would check/install $live (backup-and-overwrite if it differs from bundled)"
    continue
  fi
  if [ ! -f "$live" ]; then
    cp "$SRC/$f" "$live"
    echo "installed $live"
  elif cmp -s "$SRC/$f" "$live"; then
    echo "unchanged $live"
  else
    bak="$(unique_backup_path "$live")"
    cp "$live" "$bak"
    cp "$SRC/$f" "$live"
    echo "updated $live — your previous version saved to $bak; re-apply any customizations from it"
  fi
done

[ "$DRY" -eq 1 ] || mkdir -p "$SKILLS_DEST"
for s in $SKILLS; do
  if [ "$DRY" -eq 1 ]; then
    for sf in "$SKILLS_SRC/$s"/*; do echo "would install $SKILLS_DEST/$s/$(basename "$sf")"; done
  else
    mkdir -p "$SKILLS_DEST/$s"
    cp -r "$SKILLS_SRC/$s"/. "$SKILLS_DEST/$s"/
    echo "installed $SKILLS_DEST/$s"
  fi
done

# Base rules are plugin-owned: unconditional overwrite, version stamped from
# plugin.json. Never touches rules/customize/ — that's the user's landing
# zone, handled separately below.
[ "$DRY" -eq 1 ] || mkdir -p "$RULES_DEST"
for f in $RULES; do
  if [ "$DRY" -eq 1 ]; then
    echo "would install $RULES_DEST/$f (version $VERSION)"
  else
    cp "$RULES_SRC/$f" "$RULES_DEST/$f"
    inject_version "$RULES_DEST/$f"
    echo "installed $RULES_DEST/$f (version $VERSION)"
  fi
done

[ "$DRY" -eq 1 ] || mkdir -p "$RULES_DEST/customize"
if [ -n "$CUSTOMIZE_FILES" ]; then
  for f in $CUSTOMIZE_FILES; do
    if [ -f "$RULES_DEST/customize/$f" ]; then
      echo "skipped $RULES_DEST/customize/$f (already exists — customize/ is never overwritten)"
    elif [ "$DRY" -eq 1 ]; then
      echo "would install $RULES_DEST/customize/$f"
    else
      cp "$CUSTOMIZE_SRC/$f" "$RULES_DEST/customize/$f"
      echo "installed $RULES_DEST/customize/$f"
    fi
  done
fi

# Hooks are plugin-owned scripts: unconditional overwrite, no frontmatter to
# stamp a version into.
[ "$DRY" -eq 1 ] || mkdir -p "$HOOKS_DEST"
for f in $HOOK_FILES; do
  if [ -f "$HOOKS_SRC/$f" ]; then
    [ "$DRY" -eq 1 ] && echo "would install $HOOKS_DEST/$f" || { cp "$HOOKS_SRC/$f" "$HOOKS_DEST/$f"; echo "installed $HOOKS_DEST/$f"; }
  fi
done

# Workflows are plugin-owned scripts (code-enforced STDD phases): unconditional
# overwrite, no frontmatter to stamp a version into — same treatment as hooks.
[ "$DRY" -eq 1 ] || mkdir -p "$WORKFLOWS_DEST"
for f in $WORKFLOWS; do
  if [ "$DRY" -eq 1 ]; then
    echo "would install $WORKFLOWS_DEST/$f"
  else
    cp "$WORKFLOWS_SRC/$f" "$WORKFLOWS_DEST/$f"
    echo "installed $WORKFLOWS_DEST/$f"
  fi
done

# scripts/stdd_custody_check.py is a runtime dependency workflows/stdd-execute.js
# relays to at runtime (REQ-07/REQ-10): unconditional overwrite, same treatment
# as hooks/workflows. The rest of scripts/ (this repo's own CI tooling) is not
# installed — see the $SCRIPTS definition above.
[ "$DRY" -eq 1 ] || mkdir -p "$SCRIPTS_DEST"
for f in $SCRIPTS; do
  if [ "$DRY" -eq 1 ]; then
    echo "would install $SCRIPTS_DEST/$f"
  else
    cp "$SCRIPTS_SRC/$f" "$SCRIPTS_DEST/$f"
    echo "installed $SCRIPTS_DEST/$f"
  fi
done

# STDD skills: opt-in, --stdd-role=RD|PM|UIUX|ALL (no flag → install nothing,
# backward compatible — specs/stdd-integration.md S-35). Only ALL is
# implemented this round; RD/PM/UIUX print the deferred message and install
# nothing (no silent subset — S-33/S-35).
if [ -n "$STDD_ROLE" ]; then
  case "$STDD_ROLE" in
    RD|PM|UIUX)
      echo "此視角（${STDD_ROLE}）deferred，本輪僅支援 ALL（specs/stdd-integration.md S-33/S-35）——未安裝任何 STDD skill。"
      ;;
    ALL)
      STDD_SKILLS=$(stdd_profile_skills ALL)
      [ "$DRY" -eq 1 ] || mkdir -p "$SKILLS_DEST"
      for s in $STDD_SKILLS; do
        if [ "$DRY" -eq 1 ]; then
          echo "would install STDD skill $SKILLS_DEST/$s"
        else
          mkdir -p "$SKILLS_DEST/$s"
          cp -r "$STDD_SKILLS_SRC/$s"/. "$SKILLS_DEST/$s"/
          echo "installed STDD skill $SKILLS_DEST/$s"
        fi
      done
      if [ "$DRY" -eq 0 ]; then
        { echo "role=ALL"; printf '%s\n' $STDD_SKILLS; } > "$STDD_MANIFEST"
        echo "recorded STDD role ALL in $STDD_MANIFEST"
      fi
      ;;
  esac
fi

# STDD test-file guard hook: independent of --stdd-role (S-35). Default NOT
# installed; only registers when --install-hook is explicitly passed.
if [ "$INSTALL_HOOK" -eq 1 ]; then
  if [ "$DRY" -eq 1 ]; then
    echo "would install $HOOKS_DEST/stdd_test_guard.py and register its PreToolUse entry in $SETTINGS_JSON"
  else
    cp "$HOOKS_SRC/stdd_test_guard.py" "$HOOKS_DEST/stdd_test_guard.py"
    echo "installed $HOOKS_DEST/stdd_test_guard.py"
    if command -v python3 >/dev/null 2>&1; then
      python3 "$HOOKS_SRC/register_stdd_hook.py" "$SETTINGS_JSON" "$HOOKS_DEST/stdd_test_guard.py"
    else
      echo "WARNING: python3 not found — could not auto-register the hook in $SETTINGS_JSON." >&2
      echo "  Add manually: PreToolUse -> command: python3 \"$HOOKS_DEST/stdd_test_guard.py\"" >&2
    fi
    echo "NOTE: PreToolUse hooks are snapshotted at session start. If this install"
    echo "  ran inside an existing (or --continue/--resume'd) session, the hook will"
    echo "  NOT be active there — verify it in a brand-new session, not a resumed one."
  fi
fi

[ "$DRY" -eq 1 ] && { echo "dry-run done (nothing written)."; exit 0; }

# Record what we installed, then verify every file actually landed.
#
# verify_asset's CHECK argument ("file" or "dir") is the only behavior axis
# here — rules' combined $ALL_RULES list (built just below) already spells
# "customize/foo.md" per entry, so checking "$dest/$f" against $RULES_DEST
# naturally reaches both rules/*.md and rules/customize/*.md with the same
# "file" check as every other asset; no special-casing needed. Sets the
# global VERIFY_GOT (not a subshell return) so `exit 1` on failure aborts
# the whole script, not just a captured command substitution.
verify_asset() {
  local label="$1" dest="$2" manifest="$3" check="$4"; shift 4
  local list="$*"
  printf '%s\n' $list > "$manifest"
  local want f
  want=$(echo $list | wc -w | tr -d ' ')
  VERIFY_GOT=0
  for f in $list; do
    if [ "$check" = "dir" ]; then
      [ -d "$dest/$f" ] && VERIFY_GOT=$((VERIFY_GOT+1))
    else
      [ -f "$dest/$f" ] && VERIFY_GOT=$((VERIFY_GOT+1))
    fi
  done
  if [ "$VERIFY_GOT" -ne "$want" ]; then
    echo "ERROR: expected $want $label in $dest but found $VERIFY_GOT — partial install, re-run." >&2
    exit 1
  fi
}

verify_asset "roles"     "$DEST"           "$MANIFEST"           file $ROLES
got=$VERIFY_GOT
verify_asset "skills"    "$SKILLS_DEST"    "$SKILLS_MANIFEST"    dir  $SKILLS
got_skills=$VERIFY_GOT

ALL_RULES="$RULES"
for f in $CUSTOMIZE_FILES; do ALL_RULES="$ALL_RULES customize/$f"; done
verify_asset "rules"     "$RULES_DEST"     "$RULES_MANIFEST"     file $ALL_RULES
got_rules=$VERIFY_GOT
verify_asset "hooks"     "$HOOKS_DEST"     "$HOOKS_MANIFEST"     file $HOOK_FILES
got_hooks=$VERIFY_GOT
verify_asset "workflows" "$WORKFLOWS_DEST" "$WORKFLOWS_MANIFEST" file $WORKFLOWS
got_workflows=$VERIFY_GOT
verify_asset "scripts"   "$SCRIPTS_DEST"   "$SCRIPTS_MANIFEST"   file $SCRIPTS
got_scripts=$VERIFY_GOT

echo "install done: $got roles in $DEST (manifest: $MANIFEST), $got_skills skills in $SKILLS_DEST (manifest: $SKILLS_MANIFEST), $got_rules rules in $RULES_DEST (manifest: $RULES_MANIFEST), $got_hooks hooks in $HOOKS_DEST (manifest: $HOOKS_MANIFEST), $got_workflows workflows in $WORKFLOWS_DEST (manifest: $WORKFLOWS_MANIFEST), $got_scripts scripts in $SCRIPTS_DEST (manifest: $SCRIPTS_MANIFEST)"
echo "NOTE: open a NEW Claude Code session to load the roles and skills (both are read at session start)."

echo ""
echo "HOOKS: institution_guard.py, institution_guard.sh, pre_tool_use.sh, verify_gate.py, and dispatch_guard.py are now copied to $HOOKS_DEST."
echo "  They still need wiring into a hooks.json (PreToolUse/Stop) and the"
echo "  TLOR_INSTITUTION_GUARD / TLOR_VERIFY_GATE / TLOR_DISPATCH_GUARD env vars to activate — the"
echo "  plugin route (claude plugin add twjohnwu/tlor-orchestration) wires this"
echo "  automatically; install.sh only places the files."

echo ""
echo "ROUTING: rules already auto-load on their own (.claude/rules/ is a native auto-load location)."
echo "  Run /tlor-init to additionally generate CLAUDE.md + AGENTS.md routing: a dispatch-discipline"
echo "  reminder, an AGENTS.md interface for tools that don't read .claude/rules/, and declaring these"
echo "  roles as your primary dispatch targets."
