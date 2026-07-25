#!/usr/bin/env bash
# install.sh — copy TLOR agent roles, skills, rules, and hooks into ~/.claude/
# (no plugin system needed).
# Usage: ./install.sh [--dry-run] [--force] [--uninstall] [--with-optional]
#                      [--stdd-role=RD|PM|UIUX|ALL] [--install-hook]
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
set -euo pipefail

: "${HOME:?HOME is not set — refusing to guess an install location}"
ROOT="$(cd "$(dirname "$0")" && pwd)"
SRC="$ROOT/agents"
SKILLS_SRC="$ROOT/skills"
RULES_SRC="$ROOT/rules"
HOOKS_SRC="$ROOT/hooks"
STDD_SKILLS_SRC="$ROOT/stdd-skills"
PLUGIN_JSON="$ROOT/.claude-plugin/plugin.json"

INSTITUTION="$HOME/.claude/institution"
DEST="$HOME/.claude/agents"
SKILLS_DEST="$HOME/.claude/skills"
RULES_DEST="$HOME/.claude/rules"
HOOKS_DEST="$HOME/.claude/hooks"
SETTINGS_JSON="$HOME/.claude/settings.json"
MANIFEST="$DEST/.tlor-manifest"
SKILLS_MANIFEST="$SKILLS_DEST/.tlor-manifest"
RULES_MANIFEST="$RULES_DEST/.tlor-manifest"
HOOKS_MANIFEST="$HOOKS_DEST/.tlor-manifest"
STDD_MANIFEST="$SKILLS_DEST/.tlor-stdd-manifest"

DRY=0; FORCE=0; UNINSTALL=0; WITH_OPTIONAL=0; STDD_ROLE=""; INSTALL_HOOK=0
for a in "$@"; do
  case "$a" in
    --dry-run) DRY=1;;
    --force) FORCE=1;;
    --uninstall) UNINSTALL=1;;
    --with-optional) WITH_OPTIONAL=1;;
    --stdd-role=*) STDD_ROLE="${a#*=}";;
    --install-hook) INSTALL_HOOK=1;;
    *) echo "unknown arg: $a" >&2; exit 1;;
  esac
done

case "$STDD_ROLE" in
  ""|RD|PM|UIUX|ALL) ;;
  *) echo "unknown --stdd-role value: $STDD_ROLE (expected RD|PM|UIUX|ALL)" >&2; exit 1;;
esac

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
HOOK_FILES="institution_guard.py institution_guard.sh pre_tool_use.sh verify_gate.py"
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
  if [ -f "$MANIFEST" ]; then
    remove_src="$MANIFEST"
  else
    remove_src=""
  fi
  while IFS= read -r f || [ -n "$f" ]; do
    if ! is_safe_manifest_entry "$f"; then
      echo "WARNING: skipping unsafe manifest entry '$f' in ${remove_src:-$MANIFEST (fallback list)}" >&2
      continue
    fi
    if [ -f "$DEST/$f" ]; then
      # Preserve a customized agent file (differs from this checkout's
      # bundled copy) as a .bak before removing it — uninstall should never
      # discard a hand-edit the user never asked to lose.
      if [ -f "$SRC/$f" ] && ! cmp -s "$SRC/$f" "$DEST/$f"; then
        bak="$(unique_backup_path "$DEST/$f")"
        if [ "$DRY" -eq 1 ]; then
          echo "would preserve customized $DEST/$f -> $bak before removing"
        else
          cp "$DEST/$f" "$bak"
          echo "preserved customized $DEST/$f -> $bak"
        fi
      fi
      [ "$DRY" -eq 1 ] && echo "would remove $DEST/$f" || { rm "$DEST/$f"; echo "removed $DEST/$f"; }
    fi
  done < <(if [ -n "$remove_src" ]; then cat "$remove_src"; else printf '%s\n' $ROLES; fi)
  if [ "$DRY" -eq 0 ] && [ -f "$MANIFEST" ]; then rm "$MANIFEST"; fi

  if [ -f "$SKILLS_MANIFEST" ]; then remove_src="$SKILLS_MANIFEST"; else remove_src=""; fi
  while IFS= read -r s || [ -n "$s" ]; do
    if ! is_safe_manifest_entry "$s"; then
      echo "WARNING: skipping unsafe manifest entry '$s' in ${remove_src:-$SKILLS_MANIFEST (fallback list)}" >&2
      continue
    fi
    if [ -d "$SKILLS_DEST/$s" ]; then
      [ "$DRY" -eq 1 ] && echo "would remove $SKILLS_DEST/$s" || { rm -rf "$SKILLS_DEST/$s"; echo "removed $SKILLS_DEST/$s"; }
    fi
  done < <(if [ -n "$remove_src" ]; then cat "$remove_src"; else printf '%s\n' $SKILLS; fi)
  if [ "$DRY" -eq 0 ] && [ -f "$SKILLS_MANIFEST" ]; then rm "$SKILLS_MANIFEST"; fi

  if [ -f "$RULES_MANIFEST" ]; then remove_src="$RULES_MANIFEST"; else remove_src=""; fi
  while IFS= read -r f || [ -n "$f" ]; do
    if ! is_safe_manifest_entry "$f"; then
      echo "WARNING: skipping unsafe manifest entry '$f' in ${remove_src:-$RULES_MANIFEST (fallback list)}" >&2
      continue
    fi
    if [ -f "$RULES_DEST/$f" ]; then
      [ "$DRY" -eq 1 ] && echo "would remove $RULES_DEST/$f" || { rm "$RULES_DEST/$f"; echo "removed $RULES_DEST/$f"; }
    fi
  done < <(if [ -n "$remove_src" ]; then cat "$remove_src"; else printf '%s\n' $RULES; fi)
  # Clean up empty customize dir
  [ -d "$RULES_DEST/customize" ] && rmdir "$RULES_DEST/customize" 2>/dev/null || true
  if [ "$DRY" -eq 0 ] && [ -f "$RULES_MANIFEST" ]; then rm "$RULES_MANIFEST"; fi

  if [ -f "$HOOKS_MANIFEST" ]; then remove_src="$HOOKS_MANIFEST"; else remove_src=""; fi
  while IFS= read -r f || [ -n "$f" ]; do
    if ! is_safe_manifest_entry "$f"; then
      echo "WARNING: skipping unsafe manifest entry '$f' in ${remove_src:-$HOOKS_MANIFEST (fallback list)}" >&2
      continue
    fi
    if [ -f "$HOOKS_DEST/$f" ]; then
      [ "$DRY" -eq 1 ] && echo "would remove $HOOKS_DEST/$f" || { rm "$HOOKS_DEST/$f"; echo "removed $HOOKS_DEST/$f"; }
    fi
  done < <(if [ -n "$remove_src" ]; then cat "$remove_src"; else printf '%s\n' $HOOK_FILES; fi)
  if [ "$DRY" -eq 0 ] && [ -f "$HOOKS_MANIFEST" ]; then rm "$HOOKS_MANIFEST"; fi

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

  # STDD test-file guard hook: remove the copied script only. Un-registering
  # the settings.json entry is left to the user (rewriting someone else's
  # settings.json on uninstall without an explicit ask is a T2 action this
  # script does not take unprompted — see hooks/register_stdd_hook.py note).
  if [ -f "$HOOKS_DEST/stdd_test_guard.py" ]; then
    [ "$DRY" -eq 1 ] && echo "would remove $HOOKS_DEST/stdd_test_guard.py" || { rm "$HOOKS_DEST/stdd_test_guard.py"; echo "removed $HOOKS_DEST/stdd_test_guard.py (settings.json entry left in place — remove it by hand)"; }
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

mkdir -p "$DEST"
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

mkdir -p "$SKILLS_DEST"
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
mkdir -p "$RULES_DEST"
for f in $RULES; do
  if [ "$DRY" -eq 1 ]; then
    echo "would install $RULES_DEST/$f (version $VERSION)"
  else
    cp "$RULES_SRC/$f" "$RULES_DEST/$f"
    inject_version "$RULES_DEST/$f"
    echo "installed $RULES_DEST/$f (version $VERSION)"
  fi
done

mkdir -p "$RULES_DEST/customize"
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
mkdir -p "$HOOKS_DEST"
for f in $HOOK_FILES; do
  if [ -f "$HOOKS_SRC/$f" ]; then
    [ "$DRY" -eq 1 ] && echo "would install $HOOKS_DEST/$f" || { cp "$HOOKS_SRC/$f" "$HOOKS_DEST/$f"; echo "installed $HOOKS_DEST/$f"; }
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
      mkdir -p "$SKILLS_DEST"
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
printf '%s\n' $ROLES > "$MANIFEST"
want=$(echo $ROLES | wc -w | tr -d ' '); got=0
for f in $ROLES; do [ -f "$DEST/$f" ] && got=$((got+1)); done
if [ "$got" -ne "$want" ]; then
  echo "ERROR: expected $want files in $DEST but found $got — partial install, re-run." >&2
  exit 1
fi

printf '%s\n' $SKILLS > "$SKILLS_MANIFEST"
want_skills=$(echo $SKILLS | wc -w | tr -d ' '); got_skills=0
for s in $SKILLS; do [ -d "$SKILLS_DEST/$s" ] && got_skills=$((got_skills+1)); done
if [ "$got_skills" -ne "$want_skills" ]; then
  echo "ERROR: expected $want_skills skills in $SKILLS_DEST but found $got_skills — partial install, re-run." >&2
  exit 1
fi

ALL_RULES="$RULES"
for f in $CUSTOMIZE_FILES; do ALL_RULES="$ALL_RULES customize/$f"; done
printf '%s\n' $ALL_RULES > "$RULES_MANIFEST"
want_rules=$(echo $ALL_RULES | wc -w | tr -d ' '); got_rules=0
for f in $RULES; do [ -f "$RULES_DEST/$f" ] && got_rules=$((got_rules+1)); done
for f in $CUSTOMIZE_FILES; do [ -f "$RULES_DEST/customize/$f" ] && got_rules=$((got_rules+1)); done
if [ "$got_rules" -ne "$want_rules" ]; then
  echo "ERROR: expected $want_rules rules in $RULES_DEST but found $got_rules — partial install, re-run." >&2
  exit 1
fi

printf '%s\n' $HOOK_FILES > "$HOOKS_MANIFEST"
want_hooks=$(echo $HOOK_FILES | wc -w | tr -d ' '); got_hooks=0
for f in $HOOK_FILES; do [ -f "$HOOKS_DEST/$f" ] && got_hooks=$((got_hooks+1)); done
if [ "$got_hooks" -ne "$want_hooks" ]; then
  echo "ERROR: expected $want_hooks hooks in $HOOKS_DEST but found $got_hooks — partial install, re-run." >&2
  exit 1
fi

echo "install done: $got roles in $DEST (manifest: $MANIFEST), $got_skills skills in $SKILLS_DEST (manifest: $SKILLS_MANIFEST), $got_rules rules in $RULES_DEST (manifest: $RULES_MANIFEST), $got_hooks hooks in $HOOKS_DEST (manifest: $HOOKS_MANIFEST)"
echo "NOTE: open a NEW Claude Code session to load the roles and skills (both are read at session start)."

echo ""
echo "HOOKS: institution_guard.py, institution_guard.sh, pre_tool_use.sh, and verify_gate.py are now copied to $HOOKS_DEST."
echo "  They still need wiring into a hooks.json (PreToolUse/Stop) and the"
echo "  TLOR_INSTITUTION_GUARD / TLOR_VERIFY_GATE env vars to activate — the"
echo "  plugin route (claude plugin add twjohnwu/tlor-orchestration) wires this"
echo "  automatically; install.sh only places the files."

echo ""
echo "ROUTING: For rules to auto-load, set up CLAUDE.md + AGENTS.md routing."
echo "  Run /tlor-init in Claude Code to generate CLAUDE.md and AGENTS.md with routing."
