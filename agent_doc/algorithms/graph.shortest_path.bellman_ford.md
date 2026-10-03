---
id: graph.shortest_path.bellman_ford
name: Bellman-Ford
category: [graph, shortest-path]
confidence: high
review_required: false
sources:
  - repo: TheAlgorithms/Python
    path: graphs/bellman_ford.py
    commit: ef2ecc4d34d17ce6249ba5d3f3c17822dfd7bd50
    license: MIT
  - repo: TheAlgorithms/C-Plus-Plus
    path: dynamic_programming/bellman_ford.cpp
    commit: b64d5ecd022e4eb6b7f3f9a1157f13eccbfa6b78
    license: MIT
  - repo: williamfiset/Algorithms
    path: src/main/java/com/williamfiset/algorithms/graphtheory/BellmanFordEdgeList.java
    commit: 08c6d5f3cbee6870f480272404a271cc003b7437
    license: MIT
  - repo: ADJA/algos
    path: Graphs/BellmanFord.cpp
    commit: 244d382be168208d669db0f90ea64cc6be06e3d2
    license: MIT
  - repo: imeplusplus/icpc-notebook
    path: graphs/spfa.cpp
    commit: d6db5cb0e077ed674fd16828f3c1e452a222d103
    license: MIT
---

# Bellman-Ford

## Problem Signals
- shortest / cheapest path from one source where some edge costs may be negative
- gains and losses, refunds, discounts or exchange-rate logs modelled as edge weights
- "detect a negative cycle" or "can the total be driven down forever"
- "at most k edges" style limits on a weighted path (see Variants)
- small graph, edge list given, correctness matters more than speed

## Use When
- Edge weights can be negative and you need distances from one source.
- You must detect (and reject or report) a negative cycle reachable from the source.
- The graph is given as a plain edge list and V * E is affordable.

## Do Not Use When
- All weights are non-negative: use `graph.shortest_path.dijkstra` (much faster).
- The graph is unweighted or every edge costs the same: use `graph.traversal.bfs`.
- You need distances between all pairs on a small dense graph: use Floyd-Warshall (not in this playbook).
- The graph is a DAG: relax edges once in topological order (linear time; see `graph.topological_sort` for the ordering).

## Preconditions
- The graph is a mapping node -> iterable of (neighbour, weight) pairs, or node -> {neighbour: weight}. This is a superset of `graph.shortest_path.dijkstra`'s input, which accepts only the pairs form; when handing a graph to dijkstra use the pairs form.
- The source is a key of the mapping.
- Every neighbour that appears in an adjacency list is also a key.
- Nodes are hashable.
- Every weight is a real number (bool, NaN and infinite floats rejected); negative weights are allowed. Ints of any size are accepted.
- Weights are small enough that every candidate distance stays finite in float arithmetic; an overflowing sum is rejected with `ValueError` (it would otherwise saturate to infinity and hide a negative cycle).
- No negative-weight cycle is reachable from the source (detected at run time, raises).

## Core Invariant
After round i, `dist[v]` is at most the cost of the cheapest path from the source to `v` that uses at most i edges. A shortest path without a cycle has at most V - 1 edges, so V - 1 rounds of relaxing every edge settle all distances when no negative cycle is reachable. If a further pass over the edges still lowers some distance, a path with V edges is cheaper than every shorter one, which can only happen if it contains a negative cycle.

## Algorithm
1. Validate the input; set `dist[source] = 0` (other nodes are unknown / infinite).
2. Repeat up to V - 1 times: for every edge `(u, v, w)` whose tail `u` already has a distance, if `dist[u] + w < dist[v]` set `dist[v] = dist[u] + w`.
3. Stop early if a whole round changes nothing.
4. One more pass over all edges: if any edge can still be relaxed, a negative cycle is reachable from the source; reject.
5. Otherwise `dist` holds every reachable node; absent nodes are unreachable.

## Canonical Implementation
```python
from __future__ import annotations

import math
from numbers import Real
from typing import Dict, Hashable, Iterable, Mapping, Tuple, Union

Graph = Mapping[Hashable, Union[Iterable[Tuple[Hashable, float]], Mapping[Hashable, float]]]


def bellman_ford(graph: Graph, source: Hashable) -> Dict[Hashable, float]:
    """Shortest distance from source to every reachable node; negative edges allowed.

    Unreachable nodes are absent from the result.
    Raises ValueError for a missing node, a bad weight (bool, NaN, infinite),
    weights too large for float arithmetic, or a negative cycle reachable
    from the source.
    """
    if source not in graph:
        raise ValueError("source %r is not a node of the graph" % (source,))
    edges = []
    for u, out in graph.items():
        pairs = out.items() if isinstance(out, Mapping) else out
        for v, w in pairs:
            if v not in graph:
                raise ValueError("edge %r -> %r points to an unknown node" % (u, v))
            if isinstance(w, bool) or not isinstance(w, Real):
                raise ValueError("edge %r -> %r has invalid weight %r" % (u, v, w))
            if isinstance(w, float) and not math.isfinite(w):  # isfinite(int) can overflow
                raise ValueError("edge %r -> %r has invalid weight %r" % (u, v, w))
            edges.append((u, v, w))

    def candidate(u, v, w):
        # A saturated -inf would make every later "< dist" test False and hide a
        # negative cycle, so treat any non-finite sum as a precondition failure.
        try:
            total = dist[u] + w
        except OverflowError:  # huge int + float
            total = float("inf")
        if isinstance(total, float) and not math.isfinite(total):
            raise ValueError("edge %r -> %r: weights too large for float arithmetic" % (u, v))
        return total

    dist = {source: 0}  # type: Dict[Hashable, float]
    for _ in range(len(graph) - 1):
        changed = False
        for u, v, w in edges:
            if u in dist:
                total = candidate(u, v, w)
                if v not in dist or total < dist[v]:
                    dist[v] = total
                    changed = True
        if not changed:
            return dist  # converged early: no negative cycle is reachable
    # Verification pass: any further improvement proves a reachable negative cycle.
    for u, v, w in edges:
        if u in dist and (v not in dist or candidate(u, v, w) < dist[v]):
            raise ValueError("negative cycle reachable from source %r" % (source,))
    return dist
```

## Complexity
Time: O(V * E) — at most V - 1 rounds plus one check pass, each scanning all E edges; the early exit helps only when distances converge quickly. Space: O(V + E) for the distance map and the flattened edge list.

## Variants
- Early termination — stop after a round with no change (included above; williamfiset and ADJA both do this).
- Mark negative-cycle nodes instead of raising — keep relaxing for up to V - 1 more rounds and set every node that still improves to minus infinity (williamfiset); use when callers need the distances of the unaffected nodes.
- Path reconstruction — store `parent[v] = u` on each relaxation and walk back from the target; with a negative cycle the walk may loop, so check first.
- SPFA (queue-based) — keep a FIFO queue of nodes whose distance just improved plus an in-queue flag; usually much faster in practice, still O(V * E) worst case, and needs a per-node relaxation count to detect negative cycles.
- At most k edges — run exactly k rounds, relaxing from a copy of the previous round's distances, so a path never gains more than one edge per round.
- Detect a cycle anywhere (not only reachable) — start every node at distance 0 instead of using a single source.

## Common Failure Modes
- Test a graph with a negative edge but no negative cycle: distances must be correct (this is the reason to use the algorithm).
- Test a negative cycle reachable from the source: must raise; and a negative cycle that is NOT reachable must not raise.
- Test an undirected edge given as two directed edges with a negative weight: that is itself a negative cycle and must raise.
- Test a zero-weight cycle: must terminate with correct distances and no error.
- Test an unreachable node: it must be absent, never reported as 0 or as a huge sentinel.
- Test relaxing from a node that has no distance yet: it must be skipped (an "infinity + negative weight" sentinel can fake a path in fixed-width languages).
- Test huge weights: a `10**400` int is valid; two `-1e308` edges between two nodes must raise `ValueError` (the float sum saturates to -inf and a naive check misses the cycle).
- Test a single-node graph and a self loop (negative self loop is a negative cycle).
- Test that the verification pass runs after the last round; skipping it silently returns wrong distances.

## Production Considerations
- Python ints never overflow, but float sums do: near +-1e308 a sum saturates to infinity and `-inf + w < -inf` is False, which would miss a negative cycle, so the implementation raises on any non-finite candidate. Use integers or `Fraction` when weights are that large. In fixed-width languages a sentinel infinity must not be added to a weight, so skip unreached tails explicitly.
- Floating-point weights can make a zero-sum cycle look slightly negative; use integers or fractions when exactness matters.
- Cost is quadratic on dense graphs; for non-negative weights switch to Dijkstra, or use potentials from one Bellman-Ford run (Johnson) to reuse Dijkstra.
- The loop is iterative, so there is no recursion-depth risk.
- Source quality varies: the TheAlgorithms C++ version reserves capacity but indexes the vector, and its edge insertion uses a function-level static counter, so it is not safe to reuse as is.

## Related Algorithms
- graph.shortest_path.dijkstra — when every weight is non-negative; faster with a heap.
- graph.traversal.bfs — when the graph is unweighted.

## Representative Problems
- Given a directed network with costs that may be negative, find the cheapest way from one node to every other, or report that the cost can be lowered without bound.
- Given a table of conversion rates between currencies, decide whether a cycle of conversions yields a profit.
- Given a weighted directed graph and a limit k, find the cheapest path from a source to a target using at most k edges.
- Given difference constraints between variables, decide whether they are satisfiable by finding a feasible assignment or a contradictory cycle.

## Sources
- TheAlgorithms/Python graphs/bellman_ford.py — V - 1 rounds, skip unreached tails, a final check pass that raises on a negative cycle; the model for the canonical loop.
- TheAlgorithms/C-Plus-Plus dynamic_programming/bellman_ford.cpp — same scheme with V rounds (one more than needed, harmless); reports the cycle by printing instead of raising; implementation has memory-safety defects (see Production Considerations).
- williamfiset/Algorithms BellmanFordEdgeList.java — early exit when a round changes nothing; second phase that marks every node affected by a negative cycle as minus infinity (variant).
- ADJA/algos Graphs/BellmanFord.cpp — plain edge list, early exit; no negative-cycle detection at all (noted as a gap, not adopted).
- imeplusplus/icpc-notebook graphs/spfa.cpp (secondary) — queue-based SPFA with an in-queue flag, O(VE) worst case; used only for the SPFA variant.
- Conflict on negative-cycle handling, not on the core algorithm or complexity: raise (Python), print and return (C++), mark minus infinity (Java), ignore (ADJA). The canonical form raises ValueError; the others are in Variants.

## License Provenance
| repository | path | commit | license |
|---|---|---|---|
| TheAlgorithms/Python | graphs/bellman_ford.py | ef2ecc4d34d17ce6249ba5d3f3c17822dfd7bd50 | MIT |
| TheAlgorithms/C-Plus-Plus | dynamic_programming/bellman_ford.cpp | b64d5ecd022e4eb6b7f3f9a1157f13eccbfa6b78 | MIT |
| williamfiset/Algorithms | src/main/java/com/williamfiset/algorithms/graphtheory/BellmanFordEdgeList.java | 08c6d5f3cbee6870f480272404a271cc003b7437 | MIT |
| ADJA/algos | Graphs/BellmanFord.cpp | 244d382be168208d669db0f90ea64cc6be06e3d2 | MIT |
| imeplusplus/icpc-notebook | graphs/spfa.cpp | d6db5cb0e077ed674fd16828f3c1e452a222d103 | MIT |
