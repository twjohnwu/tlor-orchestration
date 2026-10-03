---
id: graph.shortest_path.dijkstra
name: Dijkstra's Algorithm
category: [graph, shortest-path]
confidence: high
review_required: false
sources:
  - repo: TheAlgorithms/Python
    path: graphs/dijkstra.py
    commit: ef2ecc4d34d17ce6249ba5d3f3c17822dfd7bd50
    license: MIT
  - repo: TheAlgorithms/Python
    path: graphs/dijkstra_2.py
    commit: ef2ecc4d34d17ce6249ba5d3f3c17822dfd7bd50
    license: MIT
  - repo: TheAlgorithms/C-Plus-Plus
    path: graph/dijkstra.cpp
    commit: b64d5ecd022e4eb6b7f3f9a1157f13eccbfa6b78
    license: MIT
  - repo: TheAlgorithms/C-Plus-Plus
    path: graph/bidirectional_dijkstra.cpp
    commit: b64d5ecd022e4eb6b7f3f9a1157f13eccbfa6b78
    license: MIT
  - repo: williamfiset/Algorithms
    path: src/main/java/com/williamfiset/algorithms/graphtheory/DijkstrasShortestPathAdjacencyList.java
    commit: 08c6d5f3cbee6870f480272404a271cc003b7437
    license: MIT
---

# Dijkstra's Algorithm

## Problem Signals
- shortest / cheapest / minimum-cost path from one source in a weighted graph
- edge costs are distances, times, prices or latencies, never negative
- "minimum total cost to reach every node" or "to reach a given target"
- routing, road network, network delay, cheapest itinerary
- grid or state graph where moves have different non-negative costs

## Use When
- Edge weights differ and are all non-negative, and you need distances from one source.
- You need the distance to one target and can stop as soon as it is settled.
- You need a shortest path tree (via parent pointers) from one source.

## Do Not Use When
- Any edge weight is negative: use `graph.shortest_path.bellman_ford`.
- The graph is unweighted or every edge costs the same: use `graph.traversal.bfs`.
- You need distances between all pairs of nodes on a small dense graph: use Floyd-Warshall (not in this playbook).
- You have a good admissible heuristic and one target: A* explores fewer nodes (not in this playbook).

## Preconditions
- The graph is a mapping node -> iterable of (neighbour, weight) pairs.
- The source is a key of the mapping.
- Every neighbour that appears in an adjacency list is also a key.
- Nodes are hashable.
- Every weight is a finite number that is >= 0: negative, NaN and infinite weights are rejected (zero-weight edges are fine).

## Core Invariant
Nodes leave the min-heap in nondecreasing order of tentative distance. When a node is popped for the first time its distance is final, because any other route to it must pass through a node still in the heap whose distance is at least as large, and weights cannot be negative. Stale heap entries (a larger distance for an already settled node) are skipped on pop.

## Algorithm
1. Validate the input; set `dist[source] = 0` and push `(0, source)` on a min-heap.
2. Pop the entry with the smallest distance `d` for node `u`. If `d` is larger than `dist[u]`, it is stale: skip it.
3. For each edge `(u, v, w)`, let `nd = d + w`. If `v` has no distance yet or `nd < dist[v]`, set `dist[v] = nd` and push `(nd, v)`.
4. Repeat until the heap is empty (or until the target is popped, if only one target matters).
5. `dist` holds every reachable node; absent nodes are unreachable.

## Canonical Implementation
```python
from __future__ import annotations

import heapq
from typing import Dict, Hashable, Iterable, Mapping, Tuple

Graph = Mapping[Hashable, Iterable[Tuple[Hashable, float]]]


def dijkstra(graph: Graph, source: Hashable) -> Dict[Hashable, float]:
    """Shortest distance from source to every reachable node.

    Unreachable nodes are absent from the result.
    Raises ValueError for a missing node or a negative, NaN or infinite weight.
    """
    if source not in graph:
        raise ValueError("source %r is not a node of the graph" % (source,))
    # Validate everything up front so a bad edge is never silently skipped.
    adjacency = {}
    for u, edges in graph.items():
        edges = list(edges)
        for v, w in edges:
            if v not in graph:
                raise ValueError("edge %r -> %r points to an unknown node" % (u, v))
            if not 0 <= w < float("inf"):  # also rejects NaN and infinity
                raise ValueError("edge %r -> %r has invalid weight %r" % (u, v, w))
        adjacency[u] = edges

    dist = {source: 0}  # type: Dict[Hashable, float]
    # The counter breaks ties so nodes themselves are never compared.
    heap = [(0, 0, source)]
    counter = 1
    while heap:
        d, _, u = heapq.heappop(heap)
        if d > dist[u]:
            continue  # stale entry
        for v, w in adjacency[u]:
            nd = d + w
            if v not in dist or nd < dist[v]:
                dist[v] = nd
                heapq.heappush(heap, (nd, counter, v))
                counter += 1
    return dist
```

## Complexity
Time: O((V + E) log V) with a binary heap — each edge can push one entry, each push/pop costs O(log E). For simple graphs E <= V^2, so O(log E) = O(log V) and the total is O((V + E) log V); with unbounded parallel edges the bound is O(E log E). Space: O(V + E) for the adjacency copy, the distance map and the heap (up to E lazy entries).

## Variants
- Early exit — return as soon as the target is popped (all sources agree it is settled then); other distances are incomplete.
- Path reconstruction — store `parent[v] = u` whenever `dist[v]` improves, then walk back from the target and reverse.
- Dense-graph O(V^2) — array of distances plus a linear scan for the unsettled minimum, no heap; better when E is close to V^2.
- Bidirectional — run from source and from target (on the reversed graph) and stop on a proper meeting condition; the best candidate path found so far, not the first shared node, must be compared with the sum of the two frontier tops.
- Indexed / d-ary heap with decrease-key — avoids stale entries; a d-ary heap cuts sift cost on dense graphs.
- Set-based (ordered set with erase + insert) instead of a lazy heap — same bound, no stale entries.

## Common Failure Modes
- Test a graph with a negative edge: it must raise, since results would silently be wrong.
- Test a zero-weight edge and a zero-weight cycle: must terminate with correct distances.
- Test an unreachable node: it must be absent (or infinity), not reported as 0 or -1 unless the API documents that sentinel.
- Test source == target and a single-node graph: distance 0.
- Test a node that appears only as a neighbour (not a key): reject it, or the lookup crashes mid-run.
- Test parallel edges and self loops: the cheapest parallel edge wins; a self loop never improves anything.
- Test that equal-distance heap entries do not make Python compare nodes (e.g. mixed-type or non-orderable nodes).
- Test an early-exit version: it must not stop when the target is first pushed, only when it is popped.

## Production Considerations
- Floating-point weights accumulate rounding error; use integers or fractions when exact ties matter.
- Python ints do not overflow, but fixed-width languages need a sentinel such as INF that cannot overflow when added to a weight.
- The lazy heap holds up to E entries; for huge graphs prefer an indexed heap.
- For repeated queries on a static graph consider preprocessing (contraction hierarchies, landmarks) instead of rerunning.
- The loop is iterative, so there is no recursion-depth risk.

## Related Algorithms
- graph.traversal.bfs — when every edge costs the same; linear time with a plain queue.
- heap.priority_queue — the data structure the loop depends on.
- graph.shortest_path.bellman_ford — when weights can be negative or you must detect negative cycles.

## Representative Problems
- Given a road network with travel times, find the fastest route from a depot to every other town.
- Given a directed network of links with delays, find the time for a signal sent from one node to reach all nodes, or report that some are unreachable.
- Given a grid where each cell has an entry cost, find the cheapest path between two corners.
- Find the cheapest way to convert one state into another when each transformation has a non-negative price.

## Sources
- TheAlgorithms/Python graphs/dijkstra.py — lazy min-heap loop with a visited set, early return at the destination, -1 for unreachable (the -1 sentinel is not adopted here).
- TheAlgorithms/Python graphs/dijkstra_2.py — array-based O(V^2) variant for dense graphs.
- TheAlgorithms/C-Plus-Plus graph/dijkstra.cpp — all distances start at infinity, source at 0, min-heap relaxation.
- TheAlgorithms/C-Plus-Plus graph/bidirectional_dijkstra.cpp — two searches meeting in the middle; its prose says it stops at the first vertex seen by both searches, which is only safe with a best-candidate check (noted in Variants).
- williamfiset/Algorithms DijkstrasShortestPathAdjacencyList.java — stale-entry skip, parent array for path reconstruction, early stop for a single target.
- No conflict on the core algorithm or complexity; the sources differ only in sentinels and stopping rules.

## License Provenance
| repository | path | commit | license |
|---|---|---|---|
| TheAlgorithms/Python | graphs/dijkstra.py | ef2ecc4d34d17ce6249ba5d3f3c17822dfd7bd50 | MIT |
| TheAlgorithms/Python | graphs/dijkstra_2.py | ef2ecc4d34d17ce6249ba5d3f3c17822dfd7bd50 | MIT |
| TheAlgorithms/C-Plus-Plus | graph/dijkstra.cpp | b64d5ecd022e4eb6b7f3f9a1157f13eccbfa6b78 | MIT |
| TheAlgorithms/C-Plus-Plus | graph/bidirectional_dijkstra.cpp | b64d5ecd022e4eb6b7f3f9a1157f13eccbfa6b78 | MIT |
| williamfiset/Algorithms | src/main/java/com/williamfiset/algorithms/graphtheory/DijkstrasShortestPathAdjacencyList.java | 08c6d5f3cbee6870f480272404a271cc003b7437 | MIT |
