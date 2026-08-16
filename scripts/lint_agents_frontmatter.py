#!/usr/bin/env python3
"""Lint agents/*.md frontmatter for required fields and allowed values.

Stdlib only (no PyYAML) — parses the leading `---` block with simple line
parsing (`key: value`, multi-line `key: |` blocks are skipped since we only
need to detect the key's presence).
"""
import pathlib
import sys

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
AGENTS_DIR = REPO_ROOT / "agents"

REQUIRED_FIELDS = ["name", "description", "model", "tools"]
ALLOWED_MODELS = {"haiku", "sonnet", "opus"}
ALLOWED_EFFORTS = {"low", "medium", "high", "xhigh", "max"}

# Roles that deliberately pin NOTHING: the dispatcher must pass `model`
# per call (hooks/dispatch_guard.py enforces it) and the role gets every
# tool. A pinned default here would silently serve a dispatcher who
# forgot to choose — the exact failure the design prevents. For these,
# `model`/`tools` must be ABSENT; their presence is the violation.
UNPINNED_ROLES = {"bombadil-freeagent"}


def parse_frontmatter(text: str) -> dict:
    """Return {key: raw_value_str} for top-level frontmatter keys."""
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}
    fields = {}
    current_key = None
    for line in lines[1:]:
        if line.strip() == "---":
            break
        # A new top-level key starts at column 0 with "key:" or "key: value"
        if line[:1] not in (" ", "\t") and ":" in line:
            key, _, value = line.partition(":")
            key = key.strip()
            value = value.strip()
            fields[key] = value
            current_key = key
        # indented continuation lines belong to current_key's block value —
        # not needed for our checks, so skipped.
    return fields


def main() -> int:
    if not AGENTS_DIR.is_dir():
        print(f"ERROR: agents directory not found at {AGENTS_DIR}")
        return 1

    agent_files = sorted(AGENTS_DIR.glob("*.md"))
    if not agent_files:
        print(f"ERROR: no agent files found in {AGENTS_DIR}")
        return 1

    errors = []

    for path in agent_files:
        text = path.read_text(encoding="utf-8")
        fields = parse_frontmatter(text)
        rel = path.relative_to(REPO_ROOT)

        if not fields:
            errors.append(f"{rel}: missing or malformed frontmatter block")
            continue

        if path.stem in UNPINNED_ROLES:
            for required in ("name", "description"):
                if required not in fields or not fields[required]:
                    errors.append(f"{rel}: missing required field '{required}'")
            for forbidden in ("model", "tools"):
                if forbidden in fields:
                    errors.append(
                        f"{rel}: field '{forbidden}' must be ABSENT — this role "
                        "deliberately pins neither model nor tools; the "
                        "dispatcher must pass `model` per call "
                        "(dispatch_guard.py enforces it)"
                    )
        else:
            for required in REQUIRED_FIELDS:
                if required not in fields or not fields[required]:
                    errors.append(f"{rel}: missing required field '{required}'")

        model = fields.get("model", "")
        if model and model not in ALLOWED_MODELS:
            errors.append(
                f"{rel}: field 'model' has invalid value '{model}' "
                f"(allowed: {sorted(ALLOWED_MODELS)})"
            )

        if "effort" in fields:
            effort = fields["effort"]
            if effort and effort not in ALLOWED_EFFORTS:
                errors.append(
                    f"{rel}: field 'effort' has invalid value '{effort}' "
                    f"(allowed: {sorted(ALLOWED_EFFORTS)})"
                )

    if errors:
        print(f"lint_agents_frontmatter.py: {len(errors)} violation(s):")
        for err in errors:
            print(f"  - {err}")
        return 1

    print(f"lint_agents_frontmatter.py: OK ({len(agent_files)} agent files checked)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
