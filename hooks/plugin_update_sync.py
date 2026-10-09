# -*- coding: utf-8 -*-
"""
Plugin-update auto-sync — a SessionStart hook (matcher "startup"), plugin
route only.

After a plugin-route update, installed copies of agents, base rules,
agent_doc, workflows and runtime scripts go stale until /tlor-init is
re-run, and neither hooks nor the model can invoke /tlor-init
(`disable-model-invocation: true`). This hook closes the gap for the
non-interactive part. For each install target that carries a
`.tlor-init-state` marker (~/.claude and $CLAUDE_PROJECT_DIR/.claude):

- the marker is validated first (JSON object, `version` a string if present,
  `level` "user" or "project"); an invalid marker is reported and nothing
  is written;
- only an upgrade acts: plugin.json's version must be greater than the
  marker's, compared as dotted ints. A missing or unparsable marker version
  counts as older; an unparsable plugin version keeps the hook silent;
- a user-level target (~/.claude, level "user") runs scripts/tlor_sync.py
  from ${CLAUDE_PLUGIN_ROOT} in-process, bumps the marker, and lists every
  backup path it made;
- a project-level target ($CLAUDE_PROJECT_DIR/.claude, or any marker with
  level "project") is never written — the hook only reminds the user to run
  /tlor-init there, since those files are often tracked in git.

Silent when TLOR_AUTO_SYNC is "0"/"false"/"off" (any case), when
CLAUDE_PLUGIN_ROOT is unset or empty (install.sh route — this file is not
copied there), when there is no marker, or when the marker is equal or newer.
A target whose `.tlor-sync.lock` is held (another session is syncing) is
skipped silently; a lock older than 10 minutes is treated as stale and
removed.

Never blocks: always exits 0. Any failure leaves the marker untouched,
releases the lock, and surfaces "tlor auto-sync failed: ..." instead.
"""
import importlib.util
import json
import os
import sys
import time

STATE_FILE = ".tlor-init-state"
LOCK_FILE = ".tlor-sync.lock"
STALE_LOCK_SECONDS = 600
OPT_OUT_VALUES = ("0", "false", "off")
SUCCESS_TAIL = (
    "New files apply from the next session. Run /tlor-init for optional "
    "rules / STDD / hooks / routing. Opt out: set TLOR_AUTO_SYNC=0 in "
    "~/.claude/settings.json env."
)


def _targets():
    """(target, is_project_dir) candidates, de-duplicated by real path."""
    candidates = [(os.path.join(os.path.expanduser("~"), ".claude"), False)]
    project_dir = os.environ.get("CLAUDE_PROJECT_DIR")
    if project_dir:
        candidates.append((os.path.join(project_dir, ".claude"), True))
    seen = set()
    out = []
    for target, is_project_dir in candidates:
        real = os.path.realpath(target)
        if real not in seen:
            seen.add(real)
            out.append((target, is_project_dir))
    return out


def _parse_version(value):
    """Dotted ints as a tuple, or None when value is not of that shape."""
    if not isinstance(value, str):
        return None
    parts = value.strip().split(".")
    if not all(part.isdigit() for part in parts):
        return None
    key = [int(part) for part in parts]
    while len(key) > 1 and key[-1] == 0:
        key.pop()  # 0.14 == 0.14.0
    return tuple(key)


def _read_marker(marker):
    """Load and validate the marker; raise ValueError when it is unusable."""
    with open(marker, encoding="utf-8") as fh:
        state = json.load(fh)
    if not isinstance(state, dict):
        raise ValueError("%s is not a JSON object" % marker)
    version = state.get("version")
    if version is not None and not isinstance(version, str):
        raise ValueError("%s: \"version\" is not a string" % marker)
    if state.get("level") not in ("user", "project"):
        raise ValueError("%s: \"level\" must be \"user\" or \"project\", got %r"
                         % (marker, state.get("level")))
    return state


def _load_tlor_sync(plugin_root):
    path = os.path.join(plugin_root, "scripts", "tlor_sync.py")
    spec = importlib.util.spec_from_file_location("tlor_sync", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load " + path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _acquire_lock(target):
    """Return the lock path if acquired, None if another sync holds it."""
    lock = os.path.join(target, LOCK_FILE)
    for _ in range(2):
        try:
            fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644)
        except FileExistsError:
            try:
                age = time.time() - os.path.getmtime(lock)
            except OSError:
                continue  # holder released it between our two calls
            if age <= STALE_LOCK_SECONDS:
                return None
            try:
                os.remove(lock)
            except OSError:
                return None
            continue
        os.write(fd, str(os.getpid()).encode("ascii"))
        os.close(fd)
        return lock
    return None


def _sync_target(target, is_project_dir, plugin_root):
    """Return a user-facing message, or None when nothing needed doing."""
    marker = os.path.join(target, STATE_FILE)
    if not os.path.isfile(marker):
        return None
    state = _read_marker(marker)
    tlor_sync = _load_tlor_sync(plugin_root)
    new_version = tlor_sync.read_plugin_version(plugin_root)
    new_key = _parse_version(new_version)
    if new_key is None:
        return None
    old_version = state.get("version")
    old_key = _parse_version(old_version)
    if old_key is not None and old_key >= new_key:
        return None
    old_label = old_version or "unknown"

    if is_project_dir or state["level"] == "project":
        return ("tlor %s→%s: project-level install at %s not auto-synced; "
                "run /tlor-init there." % (old_label, new_version, target))

    lock = _acquire_lock(target)
    if lock is None:
        return None
    try:
        summary = tlor_sync.sync(plugin_root, target)
        tlor_sync.write_state(target, new_version, state["level"])
    finally:
        try:
            os.remove(lock)
        except OSError:
            pass

    agents = sum(summary["agents"].values())
    rules = sum(summary["rules"].values())
    lines = ["tlor %s→%s synced to %s: %d agents (%d backed up), %d rules, "
             "agent_doc, workflows, scripts."
             % (old_label, new_version, target, agents, summary["backups"], rules)]
    if summary["backup_paths"]:
        lines.extend("Backup: " + path for path in summary["backup_paths"])
    else:
        lines.append("no backups")
    lines.append(SUCCESS_TAIL)
    return "\n".join(lines)


def main():
    if os.environ.get("TLOR_AUTO_SYNC", "").strip().lower() in OPT_OUT_VALUES:
        return 0
    plugin_root = os.environ.get("CLAUDE_PLUGIN_ROOT")
    if not plugin_root:
        return 0
    messages = []
    for target, is_project_dir in _targets():
        try:
            msg = _sync_target(target, is_project_dir, plugin_root)
        except Exception as exc:  # never block a session start
            msg = "tlor auto-sync failed: %s. Run /tlor-init manually." % (exc,)
        if msg:
            messages.append(msg)
    if messages:
        text = "\n".join(messages)
        print(json.dumps({
            "systemMessage": text,
            "hookSpecificOutput": {
                "hookEventName": "SessionStart",
                "additionalContext": text,
            },
        }))
    return 0


if __name__ == "__main__":
    try:
        main()
    except Exception:
        pass
    sys.exit(0)
