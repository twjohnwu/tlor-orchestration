# -*- coding: utf-8 -*-
import random

import pytest

from ._load import load_impl

mod = load_impl("graph.union_find")
DSU = mod.DisjointSet


def test_unit_union_and_connected():
    d = DSU(4)
    assert d.union(0, 1) is True
    assert d.union(2, 3) is True
    assert d.connected(0, 1) is True
    assert d.connected(1, 2) is False
    assert d.union(1, 3) is True
    assert d.connected(0, 2) is True


def test_unit_size_and_count():
    d = DSU(5)
    assert d.count == 5
    d.union(0, 1)
    d.union(1, 2)
    assert d.size(2) == 3
    assert d.size(4) == 1
    assert d.count == 3


def test_edge_empty_and_single():
    assert DSU(0).count == 0
    d = DSU(1)
    assert d.connected(0, 0) is True
    assert d.size(0) == 1
    assert d.count == 1
    assert d.find(0) == 0


def test_edge_duplicate_union_does_not_change_count():
    d = DSU(3)
    assert d.union(0, 1) is True
    assert d.union(1, 0) is False
    assert d.union(0, 0) is False
    assert d.count == 2


def test_edge_long_chain_no_recursion_error():
    n = 5000
    d = DSU(n)
    for i in range(n - 1):
        d.union(i, i + 1)
    assert d.connected(0, n - 1) is True
    assert d.size(0) == n
    assert d.count == 1


def test_known_example_two_components():
    # Edges of a graph with components {0,1,2} and {3,4}; node 5 isolated.
    d = DSU(6)
    res = [d.union(a, b) for a, b in [(0, 1), (1, 2), (3, 4), (2, 0)]]
    assert res == [True, True, True, False]  # last edge closes a cycle
    assert d.count == 3
    assert d.connected(0, 2) is True
    assert d.connected(2, 3) is False
    assert d.size(4) == 2


def test_known_example_random_matches_bruteforce():
    rng = random.Random(7)
    n = 30
    d = DSU(n)
    labels = list(range(n))
    for _ in range(300):
        a, b = rng.randrange(n), rng.randrange(n)
        if rng.random() < 0.5:
            assert d.union(a, b) == (labels[a] != labels[b])
            old, new = labels[b], labels[a]
            labels = [new if v == old else v for v in labels]
        else:
            assert d.connected(a, b) == (labels[a] == labels[b])
        assert d.count == len(set(labels))
        assert d.size(a) == labels.count(labels[a])


def test_precondition_reject_bad_n():
    for bad in (-1, True, 2.5, "3"):
        with pytest.raises(ValueError):
            DSU(bad)


def test_precondition_reject_unknown_element():
    d = DSU(3)
    for call in (lambda: d.union(0, 3), lambda: d.connected(-1, 0), lambda: d.size(3),
                 lambda: d.union(True, 0), lambda: d.connected(0, 1.0), lambda: d.find(-1)):
        with pytest.raises(ValueError):
            call()
    assert d.count == 3
