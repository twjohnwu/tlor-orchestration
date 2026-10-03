---
id: graph.traversal.bfs
name: Breadth-First Search
category: [graph, traversal]
confidence: high
review_required: false
sources:
  - repo: TheAlgorithms/Python
    path: graphs/breadth_first_search.py
    commit: ef2ecc4d34d17ce6249ba5d3f3c17822dfd7bd50
    license: MIT
  - repo: TheAlgorithms/Python
    path: graphs/breadth_first_search_shortest_path.py
    commit: ef2ecc4d34d17ce6249ba5d3f3c17822dfd7bd50
    license: MIT
  - repo: TheAlgorithms/C-Plus-Plus
    path: graph/breadth_first_search.cpp
    commit: b64d5ecd022e4eb6b7f3f9a1157f13eccbfa6b78
    license: MIT
  - repo: williamfiset/Algorithms
    path: src/main/java/com/williamfiset/algorithms/graphtheory/BreadthFirstSearchAdjacencyList.java
    commit: 08c6d5f3cbee6870f480272404a271cc003b7437
    license: MIT
---

# Breadth-First Search

## Problem Signals
- fewest edges / minimum number of hops / shortest path in an unweighted graph
- visit or reach every node connected to a start node
- level-by-level or layer-by-layer processing
- grid or maze where every step costs the same
- "is B reachable from A", connected component of a node

## Use When
- Every edge has the same cost and you need hop distance from one source.
- You need the set of nodes reachable from a source, in nondecreasing distance order.
- You need one shortest path (by edge count) via parent pointers.

## Do Not Use When
- Edges have different non-negative weights: use `graph.shortest_path.dijkstra`.
- You only need reachability (no distances) and the graph is very wide or shallow: the BFS frontier can reach O(V), so prefer `graph.traversal.dfs`, whose iterator-stack form grows only with depth (a push-all-neighbours DFS stack can reach O(E)).
- You need an ordering of a DAG respecting dependencies: use `graph.topological_sort`.
- Edge weights are only 0 or 1: a deque-based 0-1 BFS is the right variant (see Variants), not plain BFS.

## Preconditions
- The graph is given as an adjacency mapping node -> iterable of neighbours; each list is read exactly once, so one-shot iterators and generators are allowed.
- The source node is a key of the mapping.
- Every neighbour reached by the search is also a key; an unknown neighbour raises `ValueError` when it is encountered (lists of unreachable nodes are never read).
- Nodes are hashable.
- All edges have equal cost (distance means number of edges).

## Core Invariant
The queue holds nodes in nondecreasing distance from the source, differing by at most one level, and a node is marked visited at the moment it is enqueued, not when it is dequeued. So each node is enqueued once, and the distance recorded at that moment is the minimum edge count.

## Algorithm
1. Check the source is a key; set `dist[source] = 0` and enqueue the source.
2. While the queue is non-empty, remove the oldest node `v`.
3. For each neighbour `w` of `v` (rejecting any `w` that is not a key), if `w` has no distance yet, set `dist[w] = dist[v] + 1` (and optionally `parent[w] = v`) and enqueue it.
4. When the queue empties, `dist` holds every reachable node; absent nodes are unreachable.

## Canonical Implementation
```python
from __future__ import annotations

from collections import deque
from typing import Dict, Hashable, Iterable, Mapping


def bfs_distances(
    graph: Mapping[Hashable, Iterable[Hashable]], source: Hashable
) -> Dict[Hashable, int]:
    """Return {node: edge count from source} for every node reachable from source.

    Keys are inserted in visit order, so list(result) is the BFS order.
    """
    if source not in graph:
        raise ValueError("source %r is not a node of the graph" % (source,))

    dist = {source: 0}
    queue = deque([source])
    while queue:
        node = queue.popleft()
        for other in graph[node]:
            # Validate lazily so one-shot iterators are read only once.
            if other not in graph:
                raise ValueError(
                    "node %r lists neighbour %r that is not a key of the graph"
                    % (node, other)
                )
            # Marking on enqueue (not on dequeue) keeps each node in the queue once.
            if other not in dist:
                dist[other] = dist[node] + 1
                queue.append(other)
    return dist
```

## Complexity
Time: O(V + E) — each reachable node is enqueued and dequeued once and each adjacency list is scanned once (neighbour validation is O(1) per edge, done during the scan). Space: O(V) — the distance map and the queue hold at most all nodes.

## Variants
- Parent pointers — store `parent[w] = v` at enqueue time; walk back from the target to rebuild one shortest path.
- Early exit — return as soon as the target is dequeued or enqueued when only its distance is needed.
- Multi-source BFS — enqueue all sources with distance 0 first; gives distance to the nearest source.
- Grid BFS — neighbours are the 4 or 8 in-bounds cells that are not blocked; the grid is the implicit graph.
- Bidirectional BFS — search from both ends and stop when the frontiers meet; cuts the explored area on large graphs.
- 0-1 BFS — weights 0 or 1; push 0-weight neighbours to the front of a deque and 1-weight ones to the back.
- Boolean visited map (C++ source) — returns reachable yes/no per node instead of distances.

## Common Failure Modes
- Test a node that appears only as a neighbour (a sink with no adjacency entry): the Python source indexes the adjacency map directly and fails with a KeyError; reject or default it deliberately.
- Test a graph with a self-loop and parallel edges: no node may be enqueued twice or get a larger distance.
- Test a cycle: the search must terminate and distances must not change on the second visit.
- Test a disconnected graph: unreachable nodes are absent from the result (or reported as unreachable), not given distance 0.
- Test a source with no outgoing edges: the result is `{source: 0}`.
- Test that distance is minimal on a graph with two routes of different length (marking on dequeue instead of enqueue can enqueue duplicates and, with parent pointers, record the wrong parent).
- Test directed versus undirected input: an undirected edge needs both directions in the adjacency lists.
- Test that popping from the front of a plain list (`list.pop(0)`) is not used; it makes the loop quadratic.

## Production Considerations
- Use `collections.deque`; `list.pop(0)` is O(n) per pop.
- The loop is iterative, so there is no recursion-depth limit.
- Frontier memory can reach O(V) on wide graphs; for huge implicit graphs consider bidirectional search or an iterative-deepening alternative.
- Dict insertion order is guaranteed on Python 3.7+, which the implementation uses for visit order.
- For implicit graphs (grids, state spaces) generate neighbours lazily instead of building the full adjacency map; the implementation reads each neighbour list once, so generators work.

## Related Algorithms
- graph.traversal.dfs — when depth-first order matters, or only reachability is needed on a wide graph where the BFS frontier would be large.
- graph.shortest_path.dijkstra — when edges carry different non-negative weights.
- graph.topological_sort — when the task is an ordering of a DAG by dependencies.

## Representative Problems
- Find the minimum number of moves between two cells of a grid with obstacles.
- Find the fewest connections needed to get from one account to another in a social network.
- List all nodes reachable from a given node in a directed graph.
- Compute the level of every node in a tree given as an adjacency list.
- Find the fewest transformations from one state of a puzzle to a target state when each move costs one.

## Sources
- TheAlgorithms/Python graphs/breadth_first_search.py — queue plus visited set, mark on enqueue; the missing-adjacency-entry failure mode.
- TheAlgorithms/Python graphs/breadth_first_search_shortest_path.py — parent map for path reconstruction and the "no path" case.
- TheAlgorithms/C-Plus-Plus graph/breadth_first_search.cpp — mark on enqueue, boolean reachability result per node.
- williamfiset/Algorithms BreadthFirstSearchAdjacencyList.java — shortest path on an unweighted graph checked against Bellman-Ford; singleton and two-node edge cases; null graph rejected.
- The four sources agree on the core algorithm and O(V + E) cost (the Java README lists O(V+E)); no conflict found. Other pack files (bidirectional, 0-1 BFS, secondary notebooks) were used only for variant names.

## License Provenance
| repository | path | commit | license |
|---|---|---|---|
| TheAlgorithms/Python | graphs/breadth_first_search.py | ef2ecc4d34d17ce6249ba5d3f3c17822dfd7bd50 | MIT |
| TheAlgorithms/Python | graphs/breadth_first_search_shortest_path.py | ef2ecc4d34d17ce6249ba5d3f3c17822dfd7bd50 | MIT |
| TheAlgorithms/C-Plus-Plus | graph/breadth_first_search.cpp | b64d5ecd022e4eb6b7f3f9a1157f13eccbfa6b78 | MIT |
| williamfiset/Algorithms | src/main/java/com/williamfiset/algorithms/graphtheory/BreadthFirstSearchAdjacencyList.java | 08c6d5f3cbee6870f480272404a271cc003b7437 | MIT |
