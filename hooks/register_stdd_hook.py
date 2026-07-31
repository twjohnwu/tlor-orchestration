# -*- coding: utf-8 -*-
"""
register_stdd_hook.py — idempotently add or remove the STDD test-file
guard's PreToolUse entry in a Claude Code settings.json.

Usage:
  python3 register_stdd_hook.py <settings.json path> <hook script path>
  python3 register_stdd_hook.py <settings.json path> <hook script path> --remove

Register mode (default): creates settings.json (and its parent dir) if
missing. Never removes any existing hook entries; only appends this one if
an entry with the exact same command isn't already present. Exits non-zero
with a message on malformed existing JSON — never guesses and overwrites a
file it can't parse.

The registered entry is scoped with `"matcher": "Write|Edit|NotebookEdit"`
(matching the exact tool set stdd_test_guard.py's own tool_name check
covers) so it only fires on file-writing tool calls, not every tool
invocation. Idempotency detection still matches on the `command` string
alone (not the matcher), so a re-run against an entry registered before
this scoping was added is still recognized as "already registered".

Remove mode (`--remove`): the inverse of register — used by install.sh's
uninstall path so a deleted stdd_test_guard.py never leaves a dangling
hook registration behind (a missing script makes `python3 <path>` exit 2,
which Claude Code reads as a blocking deny on every matched tool call).
Scans EVERY hook event array under `hooks` (PreToolUse, PostToolUse, Stop,
whatever keys exist) and removes entries whose `command` matches this exact
hook script's registration string from each — never touches any other hook
entry. If removing a hook entry empties its containing block's `hooks`
list, the now-empty entry is dropped too (leaves everything else as-is).
Missing settings.json, or no matching entry anywhere, is a no-op success
(uninstall is idempotent either way). Malformed JSON, or a JSON root/`hooks`
container/event array that isn't the expected shape, is left untouched with
a clear error — never guess and overwrite a file it can't parse.

Both modes write through symlinks: if settings.json is a symlink (a common
dotfiles pattern), the rewrite targets the resolved real file so the link
itself is never replaced by a plain file.
"""
import datetime
import json
import os
import shutil
import sys


def _mentions_stdd_guard(command):
    """A PreToolUse hook entry belongs to our guard if its command MENTIONS
    stdd_test_guard.py at all — not just the exact `python3 "<path>"` string
    this installer writes. A hand-edited entry (unquoted path, python3.12,
    an unexpanded $HOME, ...) still gets caught by this substring check."""
    return isinstance(command, str) and "stdd_test_guard.py" in command


def _backup_settings(settings_path):
    """T2 protocol: back up settings.json before a destructive rewrite. A
    no-op if the file doesn't exist yet (nothing to lose)."""
    if not os.path.exists(settings_path):
        return
    timestamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    shutil.copy2(settings_path, "%s.bak-%s" % (settings_path, timestamp))


def _load_settings(settings_path):
    """Returns (settings, error_message). error_message is None on success."""
    if not os.path.exists(settings_path):
        return None, None
    with open(settings_path, "r", encoding="utf-8") as fh:
        raw = fh.read().strip()
    try:
        return (json.loads(raw) if raw else {}), None
    except json.JSONDecodeError as exc:
        return None, "%s is not valid JSON (%s) — not touching it, remove the hook entry by hand." % (settings_path, exc)


def _write_settings(settings_path, settings):
    """Write through symlinks: resolve settings_path to its real target
    first, so an `os.replace` never severs a symlink (a common dotfiles
    pattern) — it always lands on the real file the link points at."""
    real_path = os.path.realpath(settings_path)
    _backup_settings(real_path)
    tmp_path = real_path + ".tmp"
    with open(tmp_path, "w", encoding="utf-8") as fh:
        json.dump(settings, fh, indent=2, ensure_ascii=False)
        fh.write("\n")
    if os.path.exists(real_path):
        try:
            shutil.copymode(real_path, tmp_path)
        except OSError:
            pass  # e.g. read-only settings.json — fall through, os.replace still succeeds
    os.replace(tmp_path, real_path)


def register(settings_path, command):
    settings, err = _load_settings(settings_path)
    if err:
        print("ERROR: %s" % err, file=sys.stderr)
        return 1
    if settings is None:
        os.makedirs(os.path.dirname(settings_path), exist_ok=True)
        settings = {}
    elif not isinstance(settings, dict):
        print(
            "ERROR: %s root is a %s, expected a JSON object — not touching it, "
            "add the hook entry by hand." % (settings_path, type(settings).__name__),
            file=sys.stderr,
        )
        return 1

    hooks = settings.setdefault("hooks", {})
    pretool = hooks.setdefault("PreToolUse", [])

    for entry in pretool:
        for h in entry.get("hooks", []):
            if h.get("command") == command:
                print("already registered: %s" % command)
                return 0

    pretool.append({"matcher": "Write|Edit|NotebookEdit", "hooks": [{"type": "command", "command": command}]})
    _write_settings(settings_path, settings)
    print("registered: %s" % command)
    return 0


def unregister(settings_path, command):
    """Remove every hooks entry, under ANY event (PreToolUse, PostToolUse,
    Stop, whatever keys exist under `hooks`), whose command mentions
    stdd_test_guard.py — not just the exact `command` string this installer
    registered (see _mentions_stdd_guard). Container shapes that don't match
    the expected settings.json layout (a non-object JSON root, `hooks` not
    an object, an event value that isn't a list) get a clear error and
    non-zero exit rather than an AttributeError. An entry whose own `hooks`
    field couldn't be safely parsed but textually mentions the script is
    left in place and reported with an explicit WARNING; the overall exit
    code is non-zero whenever such a residual entry survives, so
    install.sh's uninstall warning fires exactly when something still needs
    a hand fix."""
    settings, err = _load_settings(settings_path)
    if err:
        print("ERROR: %s" % err, file=sys.stderr)
        return 1
    if settings is None:
        print("nothing to remove: %s does not exist" % settings_path)
        return 0
    if not isinstance(settings, dict):
        print(
            "ERROR: %s root is a %s, expected a JSON object — not touching it, "
            "remove the stdd_test_guard.py entry by hand." % (settings_path, type(settings).__name__),
            file=sys.stderr,
        )
        return 1

    hooks_container = settings.get("hooks", {})
    if not isinstance(hooks_container, dict):
        print(
            "ERROR: %s 'hooks' is a %s, expected an object — not touching it, "
            "remove the stdd_test_guard.py entry by hand."
            % (settings_path, type(hooks_container).__name__),
            file=sys.stderr,
        )
        return 1

    removed_by_event = {}
    unparseable = []  # entries mentioning the script whose shape we couldn't safely parse
    for event_name, event_list in hooks_container.items():
        if not isinstance(event_list, list):
            print(
                "ERROR: %s 'hooks.%s' is a %s, expected a list — not touching it, "
                "remove the stdd_test_guard.py entry by hand."
                % (settings_path, event_name, type(event_list).__name__),
                file=sys.stderr,
            )
            return 1

        removed_here = 0
        new_entries = []
        for entry in event_list:
            entry_hooks = entry.get("hooks") if isinstance(entry, dict) else None
            if not isinstance(entry_hooks, list):
                if "stdd_test_guard.py" in json.dumps(entry, ensure_ascii=False):
                    unparseable.append(entry)
                new_entries.append(entry)
                continue

            remaining_hooks = [
                h for h in entry_hooks
                if not _mentions_stdd_guard(h.get("command") if isinstance(h, dict) else None)
            ]
            removed_here += len(entry_hooks) - len(remaining_hooks)

            if remaining_hooks:
                new_entry = dict(entry)
                new_entry["hooks"] = remaining_hooks
                new_entries.append(new_entry)
            # an entry whose hooks list is now empty is dropped entirely

        if removed_here:
            removed_by_event[event_name] = removed_here
            hooks_container[event_name] = new_entries

    for bad in unparseable:
        print(
            "WARNING: found a hooks entry in %s mentioning stdd_test_guard.py that "
            "could not be safely parsed and was left in place — remove it by hand: %r"
            % (settings_path, bad),
            file=sys.stderr,
        )

    total_removed = sum(removed_by_event.values())
    if total_removed == 0 and not unparseable:
        print("not registered: %s" % command)
        return 0

    if total_removed:
        _write_settings(settings_path, settings)
        breakdown = ", ".join("%d from %s" % (c, e) for e, c in removed_by_event.items())
        print(
            "unregistered %d stdd_test_guard.py entr%s (%s) from %s"
            % (total_removed, "y" if total_removed == 1 else "ies", breakdown, settings_path)
        )

    return 1 if unparseable else 0


def main():
    if len(sys.argv) not in (3, 4):
        print("usage: register_stdd_hook.py <settings.json> <hook script> [--remove]", file=sys.stderr)
        return 1
    settings_path, hook_script = sys.argv[1], sys.argv[2]
    mode = sys.argv[3] if len(sys.argv) == 4 else None
    if mode not in (None, "--remove"):
        print("usage: register_stdd_hook.py <settings.json> <hook script> [--remove]", file=sys.stderr)
        return 1
    command = "python3 \"%s\"" % hook_script

    if mode == "--remove":
        return unregister(settings_path, command)
    return register(settings_path, command)


if __name__ == "__main__":
    sys.exit(main())
