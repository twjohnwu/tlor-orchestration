# -*- coding: utf-8 -*-
import random

import pytest

from ._load import load_impl

mod = load_impl("graph.traversal.dfs")
dfs = mod.dfs_preorder


def _recursive_oracle(graph, source):
    order, seen = [], set()

    def visit(node):
        seen.add(node)
        order.append(node)
        for other in graph[node]:
            if other not in seen:
                visit(other)

    visit(source)
    return order


def test_unit_depth_first_not_level_order():
    graph = {0: [1, 2], 1: [3], 2: [], 3: []}
    assert dfs(graph, 0) == [0, 1, 3, 2]


def test_unit_diamond_visits_once():
    graph = {"a": ["b", "c"], "b": ["d"], "c": ["d"], "d": []}
    assert dfs(graph, "a") == ["a", "b", "d", "c"]


def test_edge_single_node_and_self_loop():
    assert dfs({1: []}, 1) == [1]
    assert dfs({1: [1, 1]}, 1) == [1]


def test_edge_disconnected_and_cycle():
    graph = {0: [1, 1], 1: [2], 2: [0], 3: [0]}
    assert dfs(graph, 0) == [0, 1, 2]


def test_edge_long_chain_no_recursion_limit():
    n = 5000
    graph = {i: [i + 1] for i in range(n)}
    graph[n] = []
    assert dfs(graph, 0) == list(range(n + 1))


def test_edge_iterator_neighbours():
    # One-shot iterators must not be consumed before the search starts.
    graph = {1: iter([2, 3]), 2: iter([]), 3: iter([])}
    assert dfs(graph, 1) == [1, 2, 3]


def test_known_example_source_graph():
    graph = {
        "A": ["B", "C", "D"],
        "B": ["A", "D", "E"],
        "C": ["A", "F"],
        "D": ["B", "D"],
        "E": ["B", "F"],
        "F": ["C", "E", "G"],
        "G": ["F"],
    }
    assert dfs(graph, "A") == ["A", "B", "D", "E", "F", "C", "G"]


def test_known_example_randomized_against_recursive_oracle():
    rng = random.Random(11)
    for n in range(1, 30):
        graph = {i: [] for i in range(n)}
        for _ in range(rng.randint(0, n * 2)):
            graph[rng.randrange(n)].append(rng.randrange(n))
        src = rng.randrange(n)
        assert dfs(graph, src) == _recursive_oracle(graph, src)


def test_precondition_reject_missing_source():
    with pytest.raises(ValueError):
        dfs({0: [1], 1: []}, 5)


def test_precondition_reject_neighbour_not_a_key():
    with pytest.raises(ValueError):
        dfs({0: [1]}, 0)


has_cycle = mod.has_cycle


def test_cycle_diamond_is_acyclic():
    # A plain visited set would call this cyclic: node 3 is reached twice.
    diamond = {0: [1, 2], 1: [3], 2: [3], 3: []}
    assert has_cycle(diamond) is False


def test_cycle_directed_triangle_and_self_loop():
    assert has_cycle({0: [1], 1: [2], 2: [0]}) is True
    assert has_cycle({0: [0]}) is True
    assert has_cycle({0: [1], 1: [], 2: [1]}) is False


def test_cycle_undirected():
    path = {0: [1], 1: [0, 2], 2: [1]}
    triangle = {0: [1, 2], 1: [0, 2], 2: [0, 1]}
    assert has_cycle(path, directed=False) is False
    assert has_cycle(triangle, directed=False) is True
    assert has_cycle({0: [0]}, directed=False) is True
    # treated as directed, the path's parent edges are 2-cycles
    assert has_cycle(path) is True


def test_cycle_disconnected_and_validation():
    assert has_cycle({0: [], 1: [2], 2: [1]}) is True
    with pytest.raises(ValueError):
        has_cycle({0: [1]})
