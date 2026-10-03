import random

import pytest

from ._load import load_impl

impl = load_impl("string.trie")
Trie = impl.Trie


def _build(words):
    t = Trie()
    for w in words:
        t.insert(w)
    return t


def test_unit_insert_search_prefix():
    t = _build(["apple", "app", "bat"])
    assert t.search("apple") and t.search("app") and t.search("bat")
    assert not t.search("ap")
    assert t.starts_with("ap") and not t.starts_with("c")
    assert t.count_prefix("ap") == 2
    assert t.count_prefix("b") == 1
    assert t.count_prefix("z") == 0


def test_unit_delete_keeps_related_words():
    t = _build(["app", "apple"])
    assert t.delete("app") is True
    assert not t.search("app") and t.search("apple") and t.starts_with("app")
    assert t.delete("apple") is True
    assert not t.starts_with("a")
    assert t.count_prefix("") == 0


def test_unit_random_matches_brute_force():
    rng = random.Random(11)
    t = Trie()
    stored = set()
    for _ in range(400):
        w = "".join(rng.choice("abc") for _ in range(rng.randint(0, 4)))
        if rng.random() < 0.6:
            assert t.insert(w) == (w not in stored)
            stored.add(w)
        else:
            assert t.delete(w) == (w in stored)
            stored.discard(w)
        q = "".join(rng.choice("abc") for _ in range(rng.randint(0, 3)))
        assert t.search(q) == (q in stored)
        assert t.starts_with(q) == any(s.startswith(q) for s in stored)
        assert t.count_prefix(q) == sum(1 for s in stored if s.startswith(q))


def test_edge_empty_trie_and_empty_string():
    t = Trie()
    assert not t.search("") and not t.starts_with("a") and t.count_prefix("") == 0
    assert t.insert("") is True
    assert t.search("") and t.count_prefix("") == 1
    assert t.delete("") is True and not t.search("")


def test_edge_duplicates_and_missing_delete():
    t = Trie()
    assert t.insert("a") is True
    assert t.insert("a") is False
    assert t.count_prefix("a") == 1
    assert t.delete("b") is False
    assert t.delete("a") is True
    assert t.delete("a") is False
    assert t.count_prefix("a") == 0


def test_known_example_banana_family():
    words = "banana bananas bandana band apple all beast".split()
    t = _build(words)
    assert all(t.search(w) for w in words)
    assert not t.search("bandanas") and not t.search("apps")
    t.delete("all")
    assert not t.search("all")
    t.delete("banana")
    assert not t.search("banana") and t.search("bananas")
    assert t.count_prefix("ban") == 3


@pytest.mark.parametrize("bad", [None, 5, b"abc", ["a"], True])
def test_precondition_reject_non_string_key(bad):
    t = Trie()
    for call in (t.insert, t.search, t.starts_with, t.count_prefix, t.delete):
        with pytest.raises(ValueError):
            call(bad)


def test_edge_empty_prefix_convention():
    t = Trie()
    assert not t.starts_with("") and t.count_prefix("") == 0
    words = ["a", "ab", "b"]
    for w in words:
        t.insert(w)
    assert t.starts_with("") and t.count_prefix("") == len(words)
    for w in words:
        t.delete(w)
    assert not t.starts_with("") and t.count_prefix("") == 0
