# -*- coding: utf-8 -*-
"""Import a canonical implementation extracted by playbook/scripts/validate.py."""
import importlib.util
import os
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
DEFAULT_IMPL_DIR = REPO_ROOT / "playbook" / ".build" / "impl"


def load_impl(algo_id):
    impl_dir = Path(os.environ.get("PLAYBOOK_IMPL_DIR") or DEFAULT_IMPL_DIR)
    path = impl_dir / ("%s.py" % algo_id.replace(".", "_"))
    spec = importlib.util.spec_from_file_location("impl_%s" % algo_id.replace(".", "_"), str(path))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module
