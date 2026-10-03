# -*- coding: utf-8 -*-
"""Import a canonical implementation straight from its entry's python block.

PLAYBOOK_IMPL_DIR, when set, overrides: the extracted file is loaded from there.
"""
import importlib.util
import os
import sys
import types
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
ENTRIES_DIR = REPO_ROOT / "agent_doc" / "algorithms"
SCRIPTS_DIR = REPO_ROOT / "playbook" / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import validate  # noqa: E402


def load_impl(algo_id):
    stem = algo_id.replace(".", "_")
    name = "impl_%s" % stem
    override = os.environ.get("PLAYBOOK_IMPL_DIR")
    if override and (Path(override) / ("%s.py" % stem)).is_file():
        spec = importlib.util.spec_from_file_location(name, str(Path(override) / ("%s.py" % stem)))
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    text = (ENTRIES_DIR / ("%s.md" % algo_id)).read_text(encoding="utf-8")
    blocks = validate.canonical_blocks(text)
    if len(blocks) != 1:
        raise ValueError("%s: expected one python block in Canonical Implementation, found %d"
                         % (algo_id, len(blocks)))
    module = types.ModuleType(name)
    exec(compile(blocks[0], "%s.py" % stem, "exec"), module.__dict__)
    return module
