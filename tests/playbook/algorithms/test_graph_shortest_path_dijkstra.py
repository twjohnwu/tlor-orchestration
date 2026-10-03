# -*- coding: utf-8 -*-
import random

import pytest

from ._load import load_impl

mod = load_impl("graph.shortest_path.dijkstra")
dijkstra = mod.dijkstra

G = {
    "A": [("B", 2), ("C", 5)],
    "B": [("A", 2), ("D", 3), ("E", 1), ("F", 1)],
    "C": [("A", 5), ("F", 3)],
    "D": [("B", 3)],
    "E": [("B", 4), ("F", 3)],
    "F": [("C", 3), ("E", 3)],
}


def test_unit_chain_and_shortcut():
    g = {0: [(1, 1), (2, 5)], 1: [(2, 1)], 2: []}
    assert dijkstra(g, 0) == {0: 0, 1: 1, 2: 2}


def test_unit_prefers_cheaper_longer_path():
    g = {"s": [("a", 10), ("b", 1)], "b": [("a", 2)], "a": []}
    assert dijkstra(g, "s")["a"] == 3


def test_edge_single_node_and_unreachable():
    assert dijkstra({"x": []}, "x") == {"x": 0}
    d = dijkstra({"x": [], "y": []}, "x")
    assert "y" not in d


def test_edge_zero_weights_parallel_edges_self_loop():
    g = {1: [(2, 0), (2, 7), (1, 3)], 2: [(1, 0), (3, 0)], 3: []}
    assert dijkstra(g, 1) == {1: 0, 2: 0, 3: 0}


def test_edge_non_orderable_nodes_with_equal_distances():
    a, b = object(), object()
    g = {"s": [(a, 1), (b, 1)], a: [], b: []}
    d = dijkstra(g, "s")
    assert d[a] == 1 and d[b] == 1


def test_known_example_source_graph():
    d = dijkstra(G, "E")
    assert d["C"] == 6
    assert d["F"] == 3
    assert d["A"] == 6
    assert d["D"] == 7


def test_known_example_randomized_vs_floyd_warshall():
    rng = random.Random(7)
    inf = float("inf")
    for _ in range(30):
        n = rng.randint(1, 8)
        g = {i: [] for i in range(n)}
        fw = [[0 if i == j else inf for j in range(n)] for i in range(n)]
        for _ in range(rng.randint(0, 20)):
            u, v, w = rng.randrange(n), rng.randrange(n), rng.randint(0, 9)
            g[u].append((v, w))
            fw[u][v] = min(fw[u][v], w)
        for k in range(n):
            for i in range(n):
                for j in range(n):
                    fw[i][j] = min(fw[i][j], fw[i][k] + fw[k][j])
        d = dijkstra(g, 0)
        for j in range(n):
            if fw[0][j] == inf:
                assert j not in d
            else:
                assert d[j] == fw[0][j]


def test_precondition_reject_negative_edge():
    with pytest.raises(ValueError):
        dijkstra({"a": [("b", -1)], "b": []}, "a")


def test_precondition_reject_nan_weight():
    with pytest.raises(ValueError):
        dijkstra({"a": [("b", float("nan"))], "b": []}, "a")


def test_precondition_reject_missing_source():
    with pytest.raises(ValueError):
        dijkstra({"a": []}, "z")


def test_precondition_reject_unknown_neighbour():
    with pytest.raises(ValueError):
        dijkstra({"a": [("ghost", 1)]}, "a")


@pytest.mark.parametrize("bad", [float("inf"), float("-inf")])
def test_precondition_reject_infinite_weight(bad):
    with pytest.raises(ValueError):
        dijkstra({"a": [("b", bad)], "b": []}, "a")


def test_unit_float_weights():
    g = {"s": [("a", 0.5), ("b", 2.25)], "a": [("b", 1.5)], "b": []}
    assert dijkstra(g, "s") == {"s": 0, "a": 0.5, "b": 2.0}
