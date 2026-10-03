# -*- coding: utf-8 -*-
import random

import pytest

from ._load import load_impl

mod = load_impl("graph.shortest_path.bellman_ford")
bellman_ford = mod.bellman_ford
dijkstra = load_impl("graph.shortest_path.dijkstra").dijkstra


def test_unit_negative_edge_without_cycle():
    g = {0: [(1, 4), (3, 5)], 1: [], 2: [(1, -10)], 3: [(2, 3)]}
    assert bellman_ford(g, 0) == {0: 0, 1: -2, 2: 8, 3: 5}


def test_unit_mapping_of_mappings_accepted():
    g = {"a": {"b": 2, "c": 5}, "b": {"c": -1}, "c": {}}
    assert bellman_ford(g, "a") == {"a": 0, "b": 2, "c": 1}


def test_unit_matches_dijkstra_on_random_nonnegative_graphs():
    rng = random.Random(7)
    for _ in range(60):
        n = rng.randint(1, 8)
        g = {i: [] for i in range(n)}
        for _ in range(rng.randint(0, 20)):
            g[rng.randrange(n)].append((rng.randrange(n), rng.randint(0, 9)))
        assert bellman_ford(g, 0) == dijkstra(g, 0)


def test_edge_single_node_unreachable_and_self_loop():
    assert bellman_ford({"x": []}, "x") == {"x": 0}
    assert "y" not in bellman_ford({"x": [], "y": []}, "x")
    assert bellman_ford({1: [(1, 3)]}, 1) == {1: 0}


def test_edge_zero_cycle_parallel_edges_and_unreachable_negative_cycle():
    g = {1: [(2, 0), (2, 7)], 2: [(1, 0), (3, -1)], 3: []}
    assert bellman_ford(g, 1) == {1: 0, 2: 0, 3: -1}
    # the negative cycle b <-> c is not reachable from a
    h = {"a": [], "b": [("c", -1)], "c": [("b", -1)]}
    assert bellman_ford(h, "a") == {"a": 0}


def test_known_example_negative_cycle_reachable():
    edges = [(2, 1, -10), (3, 2, 3), (0, 3, 5), (0, 1, 4)]
    g = {i: [] for i in range(4)}
    for u, v, w in edges:
        g[u].append((v, w))
    assert bellman_ford(g, 0)[1] == -2
    g[1].append((3, 5))  # closes 1 -> 3 -> 2 -> 1 with total -2
    with pytest.raises(ValueError):
        bellman_ford(g, 0)


def test_known_example_matches_brute_force_on_small_negative_graphs():
    rng = random.Random(3)
    for _ in range(100):
        n = rng.randint(1, 5)
        g = {i: [] for i in range(n)}
        for _ in range(rng.randint(0, 8)):
            g[rng.randrange(n)].append((rng.randrange(n), rng.randint(-3, 6)))
        # oracle: exhaustive relaxation, with a cap that exposes a negative cycle
        best = {0: 0}
        for _ in range(n + 1):
            for u, out in g.items():
                for v, w in out:
                    if u in best and (v not in best or best[u] + w < best[v]):
                        best[v] = best[u] + w
        stable = all(v in best and best[u] + w >= best[v]
                     for u, out in g.items() if u in best for v, w in out)
        if stable:
            assert bellman_ford(g, 0) == best
        else:
            with pytest.raises(ValueError):
                bellman_ford(g, 0)


def test_precondition_reject_missing_source_and_unknown_neighbour():
    with pytest.raises(ValueError):
        bellman_ford({"a": []}, "z")
    with pytest.raises(ValueError):
        bellman_ford({"a": [("b", 1)]}, "a")


@pytest.mark.parametrize("w", [float("nan"), float("inf"), float("-inf"), True, "3", None])
def test_precondition_reject_bad_weight(w):
    with pytest.raises(ValueError):
        bellman_ford({"a": [("b", w)], "b": []}, "a")


def test_precondition_reject_negative_cycle_and_negative_self_loop():
    with pytest.raises(ValueError):
        bellman_ford({"a": [("b", 1)], "b": [("a", -2)]}, "a")
    with pytest.raises(ValueError):
        bellman_ford({"a": [("a", -1)]}, "a")


def test_edge_huge_int_weight():
    # math.isfinite(10**400) raises OverflowError; a huge int is a valid weight.
    g = {"a": [("b", 10 ** 400)], "b": [("c", -(10 ** 400))], "c": []}
    assert bellman_ford(g, "a") == {"a": 0, "b": 10 ** 400, "c": 0}


def test_edge_float_overflow_is_rejected_not_missed():
    # The sum -1e308 + -1e308 saturates to -inf; the negative cycle must not slip by.
    with pytest.raises(ValueError):
        bellman_ford({"a": [("b", -1e308)], "b": [("a", -1e308)]}, "a")
    # Same overflow on the positive side fails consistently instead of returning inf.
    with pytest.raises(ValueError):
        bellman_ford({"a": [("b", 1e308)], "b": [("c", 1e308)], "c": []}, "a")
    assert bellman_ford({"a": [("b", 1e308)], "b": []}, "a") == {"a": 0, "b": 1e308}
