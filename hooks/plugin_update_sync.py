# -*- coding: utf-8 -*-
"""
Plugin-update auto-sync — a SessionStart hook (matcher "startup").

After a plugin-route update, installed copies of agents, base rules,
agent_doc, workflows and runtime scripts go stale until /tlor-init is
re-run, and neither hooks nor the model can invoke /tlor-init
(`disable-model-invocation: true`). This hook closes the gap for the
non-interactive part: for each install target that carries a
`.tlor-init-state` marker (~/.claude and $CLAUDE_PROJECT_DIR/.claude), if the
marker's version differs from ${CLAUDE_PLUGIN_ROOT}'s plugin.json version,
it runs scripts/tlor_sync.py from the NEW plugin root in-process, bumps the
marker, and tells the user to run /tlor-init for the interactive steps.

Silent when there is no marker or the version already matches. A target
whose `.tlor-sync.lock` is held (another session is syncing) is skipped
silently; a lock older than 10 minutes is treated as stale and removed.

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


def _targets():
    """Candidate install targets, de-duplicated by real path."""
    candidates = [os.path.join(os.path.expanduser("~"), ".claude")]
    project_dir = os.environ.get("CLAUDE_PROJECT_DIR")
    if project_dir:
        candidates.append(os.path.join(project_dir, ".claude"))
    seen = set()
    out = []
    for target in candidates:
        real = os.path.realpath(target)
        if real not in seen:
            seen.add(real)
            out.append(target)
    return out


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


def _sync_target(target, plugin_root):
    """Return a user-facing message, or None when nothing needed doing."""
    marker = os.path.join(target, STATE_FILE)
    if not os.path.isfile(marker):
        return None
    with open(marker, encoding="utf-8") as fh:
        state = json.load(fh)
    tlor_sync = _load_tlor_sync(plugin_root)
    new_version = tlor_sync.read_plugin_version(plugin_root)
    old_version = state.get("version")
    if old_version == new_version:
        return None

    lock = _acquire_lock(target)
    if lock is None:
        return None
    try:
        summary = tlor_sync.sync(plugin_root, target)
        tlor_sync.write_state(target, new_version, state.get("level") or "user")
    finally:
        try:
            os.remove(lock)
        except OSError:
            pass

    agents = sum(summary["agents"].values())
    rules = sum(summary["rules"].values())
    return (
        "tlor %s→%s synced: %d agents (%d backed up), %d rules, agent_doc, "
        "workflows. Run /tlor-init for optional rules / STDD / hooks / routing."
        % (old_version, new_version, agents, summary["backups"], rules)
    )


def main():
    plugin_root = os.environ.get("CLAUDE_PLUGIN_ROOT") or os.path.dirname(
        os.path.dirname(os.path.abspath(__file__)))
    messages = []
    for target in _targets():
        try:
            msg = _sync_target(target, plugin_root)
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
