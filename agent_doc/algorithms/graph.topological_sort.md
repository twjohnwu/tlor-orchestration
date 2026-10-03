---
id: graph.topological_sort
name: Topological Sort
category: [graph, dag]
confidence: high
review_required: false
sources:
  - repo: TheAlgorithms/Python
    path: graphs/kahns_algorithm_topo.py
    commit: ef2ecc4d34d17ce6249ba5d3f3c17822dfd7bd50
    license: MIT
  - repo: TheAlgorithms/Python
    path: graphs/g_topological_sort.py
    commit: ef2ecc4d34d17ce6249ba5d3f3c17822dfd7bd50
    license: MIT
  - repo: TheAlgorithms/C-Plus-Plus
    path: graph/topological_sort.cpp
    commit: b64d5ecd022e4eb6b7f3f9a1157f13eccbfa6b78
    license: MIT
  - repo: TheAlgorithms/C-Plus-Plus
    path: graph/topological_sort_by_kahns_algo.cpp
    commit: b64d5ecd022e4eb6b7f3f9a1157f13eccbfa6b78
    license: MIT
  - repo: williamfiset/Algorithms
    path: src/main/java/com/williamfiset/algorithms/graphtheory/Kahns.java
    commit: 08c6d5f3cbee6870f480272404a271cc003b7437
    license: MIT
  - repo: williamfiset/Algorithms
    path: src/main/java/com/williamfiset/algorithms/graphtheory/TopologicalSortAdjacencyList.java
    commit: 08c6d5f3cbee6870f480272404a271cc003b7437
    license: MIT
---

# Topological Sort

## Problem Signals
- order tasks so every prerequisite comes before the task that needs it
- build order, dependency resolution, course schedule, compile order
- "linear ordering where u comes before v for every edge u -> v"
- detect whether a directed graph has a cycle (the sort fails exactly when one exists)
- process a DAG so each node is handled after all its predecessors

## Use When
- The graph is directed and you need any ordering consistent with every edge.
- You must also report that no ordering exists because of a dependency cycle.
- You want a DP over a DAG: process nodes in topological order so each node's predecessors are final.

## Do Not Use When
- The graph is undirected: there is no edge direction to order by; use `graph.traversal.dfs` or `graph.traversal.bfs` for connectivity.
- You need shortest distances, not an ordering: use `graph.traversal.bfs` (unit cost) or `graph.shortest_path.dijkstra` (weights).
- The graph may contain cycles and you still need a grouping of nodes: condense strongly connected components first, then sort the condensation (a different algorithm; not covered here).
- You need a specific tie-break order (for example the lexicographically smallest): replace the FIFO queue with a heap (see Variants) rather than using this form unchanged.

## Preconditions
- The graph is an adjacency mapping node -> iterable of successors (an edge u -> v means u must come before v); each iterable is read exactly once, so generators are allowed.
- Every node that appears as a successor is also a key; an unknown successor raises `ValueError`.
- Nodes are hashable.
- The graph is acyclic (self-loops count as cycles); a cycle raises `ValueError`, because no valid ordering exists.

## Core Invariant
A node enters the queue only when its remaining in-degree reaches zero, meaning every predecessor has already been emitted. So the emitted prefix is always consistent with all edges among emitted nodes. If the queue empties before all nodes are emitted, the unemitted nodes each still have an unemitted predecessor, which is only possible when they lie on or behind a cycle.

## Algorithm
1. Copy each adjacency iterable into a list and reject any successor that is not a key.
2. Compute `indegree[v]` = number of incoming edges (parallel edges count each time).
3. Enqueue every node with in-degree 0, in key order.
4. While the queue is non-empty: pop `u`, append it to the output, and for each successor `v` decrement `indegree[v]`; if it reaches 0, enqueue `v`.
5. If the output holds fewer nodes than the graph, a cycle exists: raise `ValueError`. Otherwise return the output.

## Canonical Implementation
```python
from __future__ import annotations

from collections import deque
from typing import Dict, Hashable, Iterable, List, Mapping


def topological_order(graph: Mapping[Hashable, Iterable[Hashable]]) -> List[Hashable]:
    """Return the nodes of a DAG so that every edge u -> v has u before v.

    Ties are broken by key order of `graph` (Kahn's algorithm, FIFO queue).
    Raises ValueError on an unknown successor or when the graph has a cycle.
    """
    # Read every adjacency iterable once, so generators are safe to pass in.
    successors = {node: list(targets) for node, targets in graph.items()}
    indegree = {node: 0 for node in successors}  # type: Dict[Hashable, int]
    for node, targets in successors.items():
        for other in targets:
            if other not in indegree:
                raise ValueError(
                    "node %r lists successor %r that is not a key of the graph"
                    % (node, other)
                )
            indegree[other] += 1

    queue = deque(node for node, count in indegree.items() if count == 0)
    order = []  # type: List[Hashable]
    while queue:
        node = queue.popleft()
        order.append(node)
        for other in successors[node]:
            indegree[other] -= 1
            if indegree[other] == 0:
                queue.append(other)

    if len(order) != len(successors):
        stuck = [node for node, count in indegree.items() if count > 0]
        raise ValueError("graph has a cycle; no topological order exists "
                         "(nodes on or behind a cycle: %r)" % (stuck,))
    return order
```

## Complexity
Time: O(V + E) — every adjacency list is copied and scanned twice and each node is enqueued and dequeued once. Space: O(V + E) — the copied adjacency lists, the in-degree map, the queue and the output.

## Variants
- DFS post-order — run a depth-first search, append a node after all its successors finish, then reverse the list (Python `g_topological_sort.py`, C++ `topological_sort.cpp`). Cycle detection needs a three-state mark (unseen / in progress / done); the sources' DFS forms do not detect cycles on their own.
- Heap instead of queue — pop the smallest ready node to get the lexicographically smallest order; time becomes O(E + V log V).
- Level-by-level Kahn — process the queue in waves; the wave count is the longest path length, useful for scheduling rounds.
- Return `None` on a cycle instead of raising (Python `kahns_algorithm_topo.py`), or throw an invalid-argument error (C++ `topological_sort.cpp`, Java `Kahns.java`); this entry raises `ValueError`.
- Count of orders / all orders — backtrack over the ready set; exponential, not covered here.

## Common Failure Modes
- Test a 3-node cycle (a -> b -> c -> a): it must raise, not return a partial order. The C++ Kahn-by-queue source has no cycle check and returns a zero-padded array on a cycle.
- Test a self-loop: it is a cycle, because the node never reaches in-degree 0.
- Test a graph with an isolated node and an empty graph: all nodes appear, and `{}` gives `[]`.
- Test duplicate (parallel) edges: in-degree must count both and both decrements must happen, or the node is never released.
- Test a node that is only a successor and has no key of its own: raise deliberately instead of a raw `KeyError`.
- Test that the result respects every edge by checking positions, not by comparing with one fixed list: many orders are valid.
- Test with a generator as an adjacency value: consuming it twice would silently drop edges.
- Test a cycle that is reachable only from some roots while other nodes are fine: the output is incomplete and must still fail.

## Production Considerations
- The Kahn loop is iterative; the DFS variant recurses to depth V and overflows Python's recursion limit on long chains, so use an explicit stack there.
- The result is deterministic given the key order of the mapping (dict insertion order on Python 3.7+); document a tie-break if callers rely on it.
- For a cycle report, the leftover nodes with positive in-degree include nodes behind the cycle, not only the cycle itself; extract an actual cycle with a DFS if the caller needs one.
- Edges added incrementally to a large graph may need an incremental topological order; this static form recomputes from scratch.

## Related Algorithms
- graph.traversal.dfs — when you want the DFS post-order form or need to extract a concrete cycle.
- graph.traversal.bfs — the queue discipline is the same; switch when you need hop distances instead of an ordering.

## Representative Problems
- Given courses and prerequisite pairs, decide whether all courses can be finished and give one valid order.
- Order the modules of a build so each is compiled after everything it imports.
- Find the length of the longest chain of dependent tasks in a task graph.
- Schedule jobs with precedence constraints into the minimum number of rounds, where independent jobs share a round.
- Check that a set of "A must come before B" rules is consistent.

## Sources
- TheAlgorithms/Python graphs/kahns_algorithm_topo.py — in-degree map, queue of zero-in-degree nodes, processed-count check against graph size to detect a cycle.
- TheAlgorithms/Python graphs/g_topological_sort.py — DFS post-order form, reversed; no cycle detection (variant only).
- TheAlgorithms/C-Plus-Plus graph/topological_sort.cpp — DFS-based form and an explicit "cycle detected" error with a cycle test.
- TheAlgorithms/C-Plus-Plus graph/topological_sort_by_kahns_algo.cpp — queue-based form; returns a padded array without any cycle check (failure mode).
- williamfiset/Algorithms Kahns.java — Kahn's algorithm, rejects cyclic input with an exception; tests include a 4-node cycle and an ordering verifier.
- williamfiset/Algorithms TopologicalSortAdjacencyList.java — documents O(V + E) time and space for the DFS-based sort.
- The sources agree on the core algorithm and O(V + E) cost across two repositories; they differ only in cycle handling (None, exception, or silently wrong), which this entry resolves by raising `ValueError`. Pack files `sorts/topological_sort.py` and `kahns_algorithm_long.py`, and the secondary `imeplusplus/icpc-notebook` `graphs/kahn.cpp` (an undirected-tolerant in-degree rule), were not used.

## License Provenance
| repository | path | commit | license |
|---|---|---|---|
| TheAlgorithms/Python | graphs/kahns_algorithm_topo.py | ef2ecc4d34d17ce6249ba5d3f3c17822dfd7bd50 | MIT |
| TheAlgorithms/Python | graphs/g_topological_sort.py | ef2ecc4d34d17ce6249ba5d3f3c17822dfd7bd50 | MIT |
| TheAlgorithms/C-Plus-Plus | graph/topological_sort.cpp | b64d5ecd022e4eb6b7f3f9a1157f13eccbfa6b78 | MIT |
| TheAlgorithms/C-Plus-Plus | graph/topological_sort_by_kahns_algo.cpp | b64d5ecd022e4eb6b7f3f9a1157f13eccbfa6b78 | MIT |
| williamfiset/Algorithms | src/main/java/com/williamfiset/algorithms/graphtheory/Kahns.java | 08c6d5f3cbee6870f480272404a271cc003b7437 | MIT |
| williamfiset/Algorithms | src/main/java/com/williamfiset/algorithms/graphtheory/TopologicalSortAdjacencyList.java | 08c6d5f3cbee6870f480272404a271cc003b7437 | MIT |
