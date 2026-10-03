# -*- coding: utf-8 -*-
import itertools
import random

import pytest

from ._load import load_impl

mod = load_impl("graph.topological_sort")
topo = mod.topological_order


def _is_valid(graph, order):
    pos = {node: i for i, node in enumerate(order)}
    if sorted(map(repr, order)) != sorted(map(repr, graph)):
        return False
    return all(pos[u] < pos[v] for u, vs in graph.items() for v in vs)


def _has_valid_order(graph):
    # Brute-force oracle: try every permutation.
    return any(_is_valid(graph, p) for p in itertools.permutations(list(graph)))


def test_unit_diamond_order_is_valid():
    graph = {"a": ["b", "c"], "b": ["d"], "c": ["d"], "d": []}
    assert _is_valid(graph, topo(graph))


def test_unit_chain_is_forced():
    assert topo({3: [2], 2: [1], 1: []}) == [3, 2, 1]


def test_unit_generator_adjacency_is_read_once():
    graph = {"a": (x for x in ["b", "c"]), "b": iter(["c"]), "c": iter([])}
    assert topo(graph) == ["a", "b", "c"]


def test_edge_empty_and_single_node():
    assert topo({}) == []
    assert topo({1: []}) == [1]


def test_edge_duplicate_edges_and_isolated_nodes():
    graph = {"a": ["b", "b"], "b": [], "z": []}
    order = topo(graph)
    assert sorted(order) == ["a", "b", "z"]
    assert order.index("a") < order.index("b")


def test_edge_tie_break_is_key_order():
    assert topo({"x": [], "y": [], "z": []}) == ["x", "y", "z"]


def test_known_example_clothes_dependencies():
    graph = {
        "underwear": ["pants", "shoes"], "pants": ["belt", "shoes"],
        "belt": ["jacket"], "jacket": [], "shoes": [], "socks": ["shoes"],
        "shirt": ["belt", "tie"], "tie": ["jacket"], "watch": [],
    }
    order = topo(graph)
    assert _is_valid(graph, order)
    assert order[0] == "underwear"


def test_known_example_exact_fifo_order():
    graph = {0: [1, 2], 1: [3], 2: [3], 3: [4, 5], 4: [], 5: []}
    assert topo(graph) == [0, 1, 2, 3, 4, 5]


def test_unit_random_dags_match_oracle():
    rng = random.Random(1234)
    for _ in range(60):
        n = rng.randint(1, 6)
        rank = list(range(n))
        rng.shuffle(rank)
        graph = {i: [] for i in range(n)}
        for u in range(n):
            for v in range(n):
                if rank[u] < rank[v] and rng.random() < 0.4:
                    graph[u].append(v)
        assert _is_valid(graph, topo(graph))


def test_unit_random_graphs_reject_iff_no_order():
    rng = random.Random(99)
    for _ in range(80):
        n = rng.randint(1, 5)
        graph = {i: [j for j in range(n) if rng.random() < 0.3] for i in range(n)}
        if _has_valid_order(graph):
            assert _is_valid(graph, topo(graph))
        else:
            with pytest.raises(ValueError):
                topo(graph)


def test_precondition_reject_three_node_cycle():
    with pytest.raises(ValueError):
        topo({"a": ["b"], "b": ["c"], "c": ["a"]})


def test_precondition_reject_self_loop():
    with pytest.raises(ValueError):
        topo({1: [1]})


def test_precondition_reject_cycle_behind_valid_prefix():
    with pytest.raises(ValueError):
        topo({"r": ["a"], "a": ["b"], "b": ["a"], "ok": []})


def test_precondition_reject_unknown_successor():
    with pytest.raises(ValueError):
        topo({"a": ["ghost"]})
