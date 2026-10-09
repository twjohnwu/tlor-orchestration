#!/usr/bin/env python3
"""Sync the plugin-owned, non-interactive parts of a tlor install.

This is the single source of truth for the part of /tlor-init that never
asks the user anything, so the same code can run from /tlor-init itself and
from the SessionStart hook (hooks/plugin_update_sync.py) after a plugin
update. It performs ONLY:

- Step 3 (agents part): every `agents/*.md` into `<target>/agents/` with
  backup-and-overwrite — missing -> install, byte-identical -> unchanged,
  different -> copy the live file to `<file>.bak-YYYYMMDD-HHMMSS` (with a
  `-2`, `-3`, ... suffix on a same-second collision) next to itself, then
  overwrite. Same algorithm as install.sh's agent-role loop.
- Step 4: every `rules/*.md` into `<target>/rules/` as an unconditional
  overwrite with `version: <plugin.json version>` injected into the
  frontmatter (same rule as install.sh's inject_version), and every
  `agent_doc/*.md` plus exactly one level of `agent_doc/<subdir>/*.md` into
  `<target>/agent_doc/`, skipping `agent_doc/customize/`.
- Step 11: every `workflows/*.js` and the runtime scripts into
  `<target>/workflows/` and `<target>/scripts/` as an unconditional
  overwrite, rewriting each destination's `.tlor-manifest`.

It never touches the institution symlink layout, `customize/` landing
zones, CLAUDE.md/AGENTS.md, STDD skills, or hooks — those are /tlor-init's
interactive steps. Existing `.tlor-manifest` files under agents/, rules/ and
agent_doc/ (written by install.sh) are refreshed so uninstall stays
accurate; none is created there if absent.

Usage:
    tlor_sync.py --target DIR [--plugin-root DIR] [--dry-run]
    tlor_sync.py --target DIR --write-state --level user|project [--plugin-root DIR]

Sync prints one JSON summary line on stdout. --write-state writes only the
`<target>/.tlor-init-state` marker ({"version", "level", "synced_at"}) that
the SessionStart hook compares against the installed plugin version.
Exit 0 on success, 1 on any error (message on stderr).

Stdlib only, Python 3.7-compatible.
"""
import argparse
import datetime
import json
import os
import shutil
import sys

DEFAULT_PLUGIN_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

STATE_FILE = ".tlor-init-state"
MANIFEST = ".tlor-manifest"

# Runtime scripts shipped to <target>/scripts/ — must match install.sh's
# $SCRIPTS list so both routes write the same manifest. The rest of scripts/
# is this repo's own CI tooling and is never installed.
RUNTIME_SCRIPTS = ("stdd_custody_check.py", "stdd_verify.py", "tlor_sync.py")


class SyncError(Exception):
    """Raised for any condition that makes the sync unsafe to complete."""


def read_plugin_version(plugin_root):
    path = os.path.join(plugin_root, ".claude-plugin", "plugin.json")
    try:
        with open(path, encoding="utf-8") as fh:
            version = json.load(fh).get("version")
    except (OSError, ValueError) as exc:
        raise SyncError("cannot read plugin version from %s: %s" % (path, exc))
    if not isinstance(version, str) or not version:
        raise SyncError("no \"version\" string in %s" % path)
    return version


def _list_files(src_dir, suffix):
    """Sorted file names directly under src_dir ending in suffix."""
    if not os.path.isdir(src_dir):
        raise SyncError("missing source directory: %s" % src_dir)
    return sorted(
        name for name in os.listdir(src_dir)
        if name.endswith(suffix) and os.path.isfile(os.path.join(src_dir, name))
    )


def _agent_doc_entries(src_dir):
    """agent_doc/*.md plus one level of <subdir>/*.md, never customize/."""
    entries = _list_files(src_dir, ".md")
    for sub in sorted(os.listdir(src_dir)):
        if sub == "customize" or not os.path.isdir(os.path.join(src_dir, sub)):
            continue
        for name in _list_files(os.path.join(src_dir, sub), ".md"):
            entries.append(sub + "/" + name)
    return entries


def inject_version(text, version):
    """Mirror install.sh's inject_version awk: replace a `version:` line in
    the leading frontmatter, or insert one before the closing `---`. A file
    without a leading `---` line is returned unchanged (apart from awk's
    newline-terminated output)."""
    lines = text.split("\n")
    if lines[-1] == "":
        lines.pop()  # awk sees no extra record after a final newline
    out = []
    in_fm = False
    done = False
    for n, line in enumerate(lines):
        if n == 0 and line == "---":
            out.append(line)
            in_fm = True
            continue
        if in_fm and line.startswith("version:"):
            out.append("version: " + version)
            done = True
            continue
        if in_fm and line == "---":
            if not done:
                out.append("version: " + version)
            out.append(line)
            in_fm = False
            continue
        out.append(line)
    return "".join(line + "\n" for line in out)


def unique_backup_path(path):
    """`<file>.bak-YYYYMMDD-HHMMSS`, suffixed -2, -3, ... if already taken."""
    base = path + ".bak-" + datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    if not os.path.exists(base):
        return base
    n = 2
    while os.path.exists("%s-%d" % (base, n)):
        n += 1
    return "%s-%d" % (base, n)


def _read_bytes(path):
    with open(path, "rb") as fh:
        return fh.read()


def _write_bytes(path, data):
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    with open(path, "wb") as fh:
        fh.write(data)


def _new_counts():
    return {"installed": 0, "updated": 0, "unchanged": 0}


def _overwrite(dest, data, counts, dry_run):
    """Unconditional overwrite; classify for the summary only."""
    if not os.path.isfile(dest):
        counts["installed"] += 1
    elif _read_bytes(dest) == data:
        counts["unchanged"] += 1
        return
    else:
        counts["updated"] += 1
    if not dry_run:
        _write_bytes(dest, data)


def _write_manifest(dest_dir, entries, dry_run, only_if_exists):
    path = os.path.join(dest_dir, MANIFEST)
    if dry_run or (only_if_exists and not os.path.isfile(path)):
        return
    _write_bytes(path, "".join(e + "\n" for e in entries).encode("utf-8"))


def sync(plugin_root, target, dry_run=False):
    """Run the non-interactive sync; return the summary dict."""
    plugin_root = os.path.abspath(plugin_root)
    target = os.path.abspath(target)
    version = read_plugin_version(plugin_root)
    if not os.path.isdir(target):
        raise SyncError("target directory does not exist: %s" % target)

    summary = {"version": version, "target": target, "dry_run": dry_run}
    backups = []

    # Step 3, agents part: backup-and-overwrite.
    src = os.path.join(plugin_root, "agents")
    dest = os.path.join(target, "agents")
    roles = _list_files(src, ".md")
    counts = _new_counts()
    for name in roles:
        data = _read_bytes(os.path.join(src, name))
        live = os.path.join(dest, name)
        if not os.path.isfile(live):
            counts["installed"] += 1
            if not dry_run:
                _write_bytes(live, data)
        elif _read_bytes(live) == data:
            counts["unchanged"] += 1
        else:
            counts["updated"] += 1
            bak = unique_backup_path(live)
            backups.append(bak)
            if not dry_run:
                shutil.copy2(live, bak)
                _write_bytes(live, data)
    _write_manifest(dest, roles, dry_run, only_if_exists=True)
    summary["agents"] = counts

    # Step 4: base rules (version-stamped) and agent_doc, unconditional.
    src = os.path.join(plugin_root, "rules")
    dest = os.path.join(target, "rules")
    rules = _list_files(src, ".md")
    counts = _new_counts()
    for name in rules:
        text = _read_bytes(os.path.join(src, name)).decode("utf-8")
        _overwrite(os.path.join(dest, name),
                   inject_version(text, version).encode("utf-8"), counts, dry_run)
    _write_manifest(dest, rules, dry_run, only_if_exists=True)
    summary["rules"] = counts

    src = os.path.join(plugin_root, "agent_doc")
    dest = os.path.join(target, "agent_doc")
    docs = _agent_doc_entries(src)
    counts = _new_counts()
    for entry in docs:
        _overwrite(os.path.join(dest, entry),
                   _read_bytes(os.path.join(src, entry)), counts, dry_run)
    _write_manifest(dest, docs, dry_run, only_if_exists=True)
    summary["agent_doc"] = counts

    # Step 11: workflows and runtime scripts, unconditional, manifest always.
    src = os.path.join(plugin_root, "workflows")
    dest = os.path.join(target, "workflows")
    workflows = _list_files(src, ".js")
    counts = _new_counts()
    for name in workflows:
        _overwrite(os.path.join(dest, name),
                   _read_bytes(os.path.join(src, name)), counts, dry_run)
    _write_manifest(dest, workflows, dry_run, only_if_exists=False)
    summary["workflows"] = counts

    src = os.path.join(plugin_root, "scripts")
    dest = os.path.join(target, "scripts")
    counts = _new_counts()
    for name in RUNTIME_SCRIPTS:
        path = os.path.join(src, name)
        if not os.path.isfile(path):
            raise SyncError("missing runtime script: %s" % path)
        _overwrite(os.path.join(dest, name), _read_bytes(path), counts, dry_run)
    _write_manifest(dest, list(RUNTIME_SCRIPTS), dry_run, only_if_exists=False)
    summary["scripts"] = counts

    summary["backups"] = len(backups)
    summary["backup_paths"] = backups
    return summary


def write_state(target, version, level):
    """Atomically write `<target>/.tlor-init-state`."""
    if level not in ("user", "project"):
        raise SyncError("level must be 'user' or 'project', got %r" % level)
    state = {
        "version": version,
        "level": level,
        "synced_at": datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    path = os.path.join(os.path.abspath(target), STATE_FILE)
    tmp = path + ".tmp.%d" % os.getpid()
    _write_bytes(tmp, (json.dumps(state) + "\n").encode("utf-8"))
    os.replace(tmp, path)
    return state


def main(argv=None):
    parser = argparse.ArgumentParser(description="Sync plugin-owned tlor files into a target .claude dir.")
    parser.add_argument("--plugin-root", default=DEFAULT_PLUGIN_ROOT)
    parser.add_argument("--target", required=True)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--write-state", action="store_true")
    parser.add_argument("--level", choices=("user", "project"))
    args = parser.parse_args(argv)

    try:
        if args.write_state:
            if not args.level:
                parser.error("--write-state requires --level user|project")
            state = write_state(args.target, read_plugin_version(args.plugin_root), args.level)
            print(json.dumps(state))
        else:
            print(json.dumps(sync(args.plugin_root, args.target, args.dry_run)))
    except (SyncError, OSError, UnicodeDecodeError) as exc:
        sys.stderr.write("tlor_sync: error: %s\n" % exc)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
