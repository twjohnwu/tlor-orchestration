# -*- coding: utf-8 -*-
import random

import pytest

from ._load import load_impl

mod = load_impl("graph.traversal.bfs")
bfs = mod.bfs_distances


def _oracle(graph, source):
    # Bellman-Ford style relaxation, unit weights.
    dist = {source: 0}
    changed = True
    while changed:
        changed = False
        for u in list(dist):
            for v in graph[u]:
                if v not in dist or dist[v] > dist[u] + 1:
                    dist[v] = dist[u] + 1
                    changed = True
    return dist


def test_unit_distances_on_small_graph():
    graph = {"a": ["b", "c"], "b": ["d"], "c": ["d"], "d": []}
    assert bfs(graph, "a") == {"a": 0, "b": 1, "c": 1, "d": 2}


def test_unit_visit_order_is_by_level():
    graph = {0: [1, 2], 1: [3], 2: [3], 3: []}
    assert list(bfs(graph, 0)) == [0, 1, 2, 3]


def test_edge_single_node_and_self_loop():
    assert bfs({1: []}, 1) == {1: 0}
    assert bfs({1: [1, 1]}, 1) == {1: 0}


def test_edge_disconnected_and_duplicates():
    graph = {0: [1, 1], 1: [0], 2: [3], 3: [2]}
    assert bfs(graph, 0) == {0: 0, 1: 1}


def test_edge_cycle_terminates():
    graph = {0: [1], 1: [2], 2: [0]}
    assert bfs(graph, 1) == {1: 0, 2: 1, 0: 2}


def test_known_example_grid_graph():
    # 0 - 1 - 2
    # |   |   |
    # 3   4   5
    #  \ / \ /
    #   6 - 7  (plus 6-7)
    edges = [(0, 1), (1, 2), (0, 3), (1, 4), (2, 5), (3, 6), (4, 6), (4, 7), (5, 7), (6, 7)]
    graph = {i: [] for i in range(8)}
    for u, v in edges:
        graph[u].append(v)
        graph[v].append(u)
    dist = bfs(graph, 0)
    assert dist[7] == 3
    assert dist == {0: 0, 1: 1, 3: 1, 2: 2, 4: 2, 6: 2, 5: 3, 7: 3}


def test_known_example_randomized_against_oracle():
    rng = random.Random(7)
    for n in range(1, 25):
        graph = {i: [] for i in range(n)}
        for _ in range(rng.randint(0, n * 2)):
            graph[rng.randrange(n)].append(rng.randrange(n))
        src = rng.randrange(n)
        assert bfs(graph, src) == _oracle(graph, src)


def test_precondition_reject_missing_source():
    with pytest.raises(ValueError):
        bfs({0: [1], 1: []}, 5)


def test_precondition_reject_neighbour_not_a_key():
    with pytest.raises(ValueError):
        bfs({0: [1]}, 0)


def test_edge_iterator_neighbours():
    # One-shot iterators must not be consumed before the search starts.
    graph = {1: iter([2, 3]), 2: iter([]), 3: iter([])}
    assert bfs(graph, 1) == {1: 0, 2: 1, 3: 1}
