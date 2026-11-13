# -*- coding: utf-8 -*-
"""Guard checks for agent_doc/security/ (INDEX, entry format, ids).

Plain text-content assertions against the real, checked-in files.
"""
import re

import pytest

from conftest import REPO_ROOT

SECURITY_DIR = REPO_ROOT / "agent_doc" / "security"
INDEX_MD = SECURITY_DIR / "INDEX.md"
NON_ENTRIES = {"README.md", "INDEX.md", "standards-map.md"}

# The full planned entry set; Related Entries may name any of these.
PLANNED_IDS = [
    "input.injection",
    "authn.authentication",
    "authn.session",
    "authz.access_control",
    "crypto.secrets",
    "files.upload_and_paths",
    "network.ssrf_outbound",
    "data.deserialization",
    "ops.logging_errors",
    "supply.dependencies",
    "api.web_api",
    "llm.applications",
]

FRONTMATTER_KEYS = ["id", "name", "category", "confidence", "verified", "sources"]

SECTIONS = [
    "Task Signals",
    "Applies When",
    "Does Not Apply When",
    "Requirements",
    "Implementation Notes",
    "Review Checklist",
    "Common Failure Modes",
    "Test Ideas",
    "Related Entries",
    "Sources",
    "License Provenance",
]


def _entry_files():
    return sorted(p for p in SECURITY_DIR.glob("*.md") if p.name not in NON_ENTRIES)


def _index_ids():
    ids = []
    for line in INDEX_MD.read_text(encoding="utf-8").splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if not line.startswith("|") or not cells or cells[0] in ("id", "") or set(cells[0]) <= set("-: "):
            continue
        ids.append(cells[0])
    return ids


def _split(path):
    """Return (frontmatter_text, body_text) of an entry file."""
    text = path.read_text(encoding="utf-8")
    match = re.match(r"^---\n(.*?)\n---\n(.*)$", text, re.DOTALL)
    assert match, f"{path.name}: missing YAML frontmatter"
    return match.group(1), match.group(2)


def _section(body, name):
    match = re.search(
        r"^## " + re.escape(name) + r"\n(.*?)(?=^## |\Z)", body, re.DOTALL | re.MULTILINE
    )
    assert match, f"missing section {name!r}"
    return match.group(1)


def test_index_rows_and_entry_files_match():
    ids = _index_ids()
    assert ids, "INDEX.md has no rows"
    assert len(ids) == len(set(ids)), f"duplicate INDEX ids: {ids}"
    for entry_id in ids:
        assert (SECURITY_DIR / f"{entry_id}.md").is_file(), f"INDEX row {entry_id!r} has no entry file"
    file_ids = [p.stem for p in _entry_files()]
    for file_id in file_ids:
        assert file_id in ids, f"entry file {file_id}.md has no INDEX row"


@pytest.mark.parametrize("path", _entry_files(), ids=lambda p: p.name)
def test_entry_has_frontmatter_keys_and_sections_in_order(path):
    front, body = _split(path)
    keys = re.findall(r"^([A-Za-z_]+):", front, re.MULTILINE)
    assert keys == FRONTMATTER_KEYS, f"{path.name}: frontmatter keys {keys}"
    headings = re.findall(r"^## (.+?)\s*$", body, re.MULTILINE)
    assert headings == SECTIONS, f"{path.name}: section headings {headings}"


@pytest.mark.parametrize("path", _entry_files(), ids=lambda p: p.name)
def test_entry_id_equals_file_name(path):
    front, _ = _split(path)
    match = re.search(r"^id:\s*(\S+)\s*$", front, re.MULTILINE)
    assert match, f"{path.name}: no id in frontmatter"
    assert match.group(1) == path.stem


@pytest.mark.parametrize("path", _entry_files(), ids=lambda p: p.name)
def test_entry_sources_have_https_url_and_provenance_says_mit(path):
    _, body = _split(path)
    assert "https://" in _section(body, "Sources"), f"{path.name}: Sources has no https:// URL"
    assert "MIT" in _section(body, "License Provenance"), f"{path.name}: License Provenance lacks 'MIT'"


@pytest.mark.parametrize("path", _entry_files(), ids=lambda p: p.name)
def test_related_entries_use_planned_ids(path):
    _, body = _split(path)
    related = _section(body, "Related Entries")
    found = re.findall(r"^- ([a-z_]+\.[a-z_]+)\b", related, re.MULTILINE)
    assert found, f"{path.name}: Related Entries lists no ids"
    for related_id in found:
        assert related_id in PLANNED_IDS, f"{path.name}: unknown related id {related_id!r}"


@pytest.mark.parametrize("path", _entry_files(), ids=lambda p: p.name)
def test_entry_length_is_60_to_200_lines(path):
    count = len(path.read_text(encoding="utf-8").splitlines())
    assert 60 <= count <= 200, f"{path.name}: {count} lines"


@pytest.mark.parametrize(
    "rel_path",
    ["agents/gondor-builder.md", "agents/orc-saboteur.md", "agents/eagle-sentinel.md"],
)
def test_role_references_security_readme(rel_path):
    text = (REPO_ROOT / rel_path).read_text(encoding="utf-8")
    assert "agent_doc/security/README.md" in text
