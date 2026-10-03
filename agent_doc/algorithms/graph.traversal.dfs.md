---
id: graph.traversal.dfs
name: Depth-First Search
category: [graph, traversal]
confidence: high
review_required: false
sources:
  - repo: TheAlgorithms/Python
    path: graphs/depth_first_search.py
    commit: ef2ecc4d34d17ce6249ba5d3f3c17822dfd7bd50
    license: MIT
  - repo: TheAlgorithms/Python
    path: graphs/depth_first_search_2.py
    commit: ef2ecc4d34d17ce6249ba5d3f3c17822dfd7bd50
    license: MIT
  - repo: TheAlgorithms/C-Plus-Plus
    path: graph/depth_first_search.cpp
    commit: b64d5ecd022e4eb6b7f3f9a1157f13eccbfa6b78
    license: MIT
  - repo: TheAlgorithms/C-Plus-Plus
    path: graph/depth_first_search_with_stack.cpp
    commit: b64d5ecd022e4eb6b7f3f9a1157f13eccbfa6b78
    license: MIT
  - repo: williamfiset/Algorithms
    path: src/main/java/com/williamfiset/algorithms/graphtheory/DepthFirstSearchAdjacencyListRecursive.java
    commit: 08c6d5f3cbee6870f480272404a271cc003b7437
    license: MIT
---

# Depth-First Search

## Problem Signals
- visit or reach every node connected to a start node
- connected component of a node, "is B reachable from A"
- explore as deep as possible before backing up
- count or list nodes reachable from a source
- detect a cycle (`has_cycle`), find bridges, or compute strongly connected components (DFS is the base traversal)
- enumerate paths or states by trying a choice, going deeper, then undoing it

## Use When
- You need reachability or the set of nodes connected to a source and hop distance does not matter.
- You need a depth-first preorder of the nodes reachable from a source.
- You are building a larger algorithm that needs DFS discovery/finish order (components, cycle checks, bridges, SCC).

## Do Not Use When
- You need the fewest edges to a target: use `graph.traversal.bfs`.
- You need an ordering of a DAG that respects dependencies: use `graph.topological_sort` (its canonical form is Kahn's algorithm; the DFS finish-order form is a variant there, not plain preorder).
- You are enumerating all paths or combinations with undo of state: use `backtracking.backtracking`.
- Edges carry different weights and you need cheapest paths: use `graph.shortest_path.dijkstra`.

## Preconditions
- The graph is given as an adjacency mapping node -> iterable of neighbours; each list is read exactly once, so one-shot iterators and generators are allowed.
- The source node is a key of the mapping; otherwise reject with `ValueError`.
- Every neighbour reached by the search is also a key; an unknown neighbour raises `ValueError` when it is encountered (lists of unreachable nodes are never read).
- Nodes are hashable.

## Core Invariant
Each node is marked visited at the moment it is first discovered, and the stack holds exactly the chain of nodes from the source to the node being expanded, each with a half-consumed neighbour iterator. The search always continues from the deepest node that still has an unread neighbour, so every node is discovered once and descendants are fully explored before the search backs up.

## Algorithm
1. Check the source is a key; mark it visited, append it to the output, push an iterator over its neighbours.
2. While the stack is non-empty, read the next neighbour `w` from the iterator on top of the stack (rejecting any `w` that is not a key).
3. If `w` is unvisited, mark it, append it to the output, and push an iterator over its neighbours; continue from step 2.
4. If the top iterator is exhausted, pop it.
5. When the stack empties, the output is the depth-first preorder of everything reachable from the source.

## Canonical Implementation
```python
from __future__ import annotations

from typing import Hashable, Iterable, Iterator, List, Mapping


def dfs_preorder(
    graph: Mapping[Hashable, Iterable[Hashable]], source: Hashable
) -> List[Hashable]:
    """Return the nodes reachable from source in depth-first preorder.

    Neighbours are tried in the order their list yields them.
    """
    if source not in graph:
        raise ValueError("source %r is not a node of the graph" % (source,))

    order = [source]
    seen = {source}
    # path[i] is the node whose neighbour iterator is stack[i].
    path = [source]
    stack = [iter(graph[source])]  # type: List[Iterator[Hashable]]
    while stack:
        for other in stack[-1]:
            # Validate lazily so one-shot iterators are read only once.
            if other not in graph:
                raise ValueError(
                    "node %r lists neighbour %r that is not a key of the graph"
                    % (path[-1], other)
                )
            if other not in seen:
                # Mark on discovery; descend before reading any further sibling.
                seen.add(other)
                order.append(other)
                path.append(other)
                stack.append(iter(graph[other]))
                break
        else:
            stack.pop()
            path.pop()
    return order


def has_cycle(graph: Mapping[Hashable, Iterable[Hashable]], directed: bool = True) -> bool:
    """Return True if the graph contains a cycle (a self-loop counts).

    directed=True: a cycle is an edge back to a node still on the DFS path.
    directed=False: every edge is listed in both directions; the edge back to the
    immediate parent is skipped once, and any other revisit of a seen node is a cycle.
    """
    done = set()  # type: set
    for root in graph:
        if root in done:
            continue
        on_path = {root}
        # Frames are [node, parent, neighbour iterator, parent edge already skipped].
        stack = [[root, None, iter(graph[root]), False]]
        while stack:
            frame = stack[-1]
            node = frame[0]
            for other in frame[2]:
                if other not in graph:
                    raise ValueError(
                        "node %r lists neighbour %r that is not a key of the graph"
                        % (node, other)
                    )
                if directed:
                    if other in on_path:
                        return True  # back edge to a node still being expanded
                    if other in done:
                        continue  # finished earlier: a cross or forward edge, not a cycle
                else:
                    if other == frame[1] and not frame[3]:
                        frame[3] = True  # the edge we arrived by
                        continue
                    if other in on_path or other in done:
                        return True  # any other revisit closes a cycle
                on_path.add(other)
                stack.append([other, node, iter(graph[other]), False])
                break
            else:
                stack.pop()
                on_path.discard(node)
                done.add(node)
    return False
```

## Complexity
Time: O(V + E) — each reachable node is pushed and popped once and each adjacency list is scanned once, with O(1) set lookups. Space: O(V) — the visited set, output and stack hold at most one entry per node (the stack holds iterators, not pushed copies of every neighbour).

## Variants
- Recursive DFS — `visit(v)`: mark `v`, then call `visit(w)` for each unvisited neighbour; same output, but depth is limited by the interpreter recursion limit.
- Push-all-neighbours stack (Python and C++ stack sources) — pop a node, push all its unvisited neighbours; simpler, but the stack can reach O(E), and the visit order matches recursive DFS only if the node is marked when popped and already-visited pops are skipped.
- Cycle detection — `has_cycle` above. Directed: three states (unseen / on the current path / done); an edge to an on-path node is a cycle, an edge to a done node is not. Undirected: skip the edge back to the immediate parent, and any other revisit is a cycle. A plain visited set cannot do either job (see Common Failure Modes).
- Discovery and finish times — record a counter on entry and exit of each node; the basis of topological sort, bridges and SCC.
- Whole-graph DFS — loop over every node as a source to cover all components.
- Counting reachable nodes — return a count instead of the order (Java source).
- Backtracking form — unmark the node on exit to explore all simple paths (a secondary notebook source shows this; see `backtracking.backtracking`).

## Common Failure Modes
- Test a node that appears only as a neighbour (a sink with no adjacency entry): the Python source indexes the mapping directly and raises a KeyError; reject or default it deliberately.
- Test cycle detection against a plain visited set, which cannot do it: the diamond 0->1, 0->2, 1->3, 2->3 is acyclic yet node 3 is seen twice, so "seen again means cycle" reports a false cycle; likewise every undirected edge is listed in both directions, so the parent edge looks like a cycle. Use three states for directed graphs and parent-skipping for undirected ones.
- Test a cycle and a self-loop: the search must terminate and no node may be output twice.
- Test a diamond (two routes to the same node): the node is output once, at its first discovery.
- Test a graph where the push-all-neighbours form marks nodes only when popped: the same node can sit on the stack many times and the result can differ from true DFS order; mark on discovery in the iterator form.
- Test that the order is a real depth-first preorder, not a level order: in `{0: [1, 2], 1: [3], 2: [], 3: []}` the result is `[0, 1, 3, 2]`.
- Test a disconnected graph: unreachable nodes are absent from the result.
- Test a long chain (a few thousand nodes) so a recursive version hitting the recursion limit is caught.
- Test a variant that loops over all vertices instead of only the neighbours of the current node (as one Python source does): it visits unrelated nodes and is not DFS.
- Test one-shot iterator neighbour lists: they must not be consumed before the search starts.

## Production Considerations
- The iterative iterator-stack form has no recursion-depth limit; Python's recursive form fails near 1000 frames by default.
- Mark on discovery (iterator stack) or skip visited nodes on pop (push-all stack); never test visited only at push time with a plain stack and expect true DFS order.
- Dict insertion order is guaranteed on Python 3.7+; the result order depends on the neighbour order each list yields.
- For implicit graphs (grids, puzzle states), generate neighbours lazily; the implementation reads each list once, so generators work.
- Directed versus undirected: an undirected edge needs both directions in the adjacency lists.
- Recursive form memory is O(depth) call frames; the iterator stack is the same asymptotically but with much smaller frames.

## Related Algorithms
- graph.traversal.bfs — when you need fewest edges or level order.
- graph.topological_sort — when the task is a dependency ordering of a DAG (canonical form is Kahn's algorithm; the DFS finish-order form is its variant).
- backtracking.backtracking — when you enumerate paths or choices and must undo state on the way back.

## Representative Problems
- Decide whether one account can be reached from another through a directed set of links.
- Count the nodes in the connected component that contains a given node.
- Count the connected regions of a grid of open and blocked cells.
- Find whether a directed graph contains a cycle.
- List the nodes of a tree in preorder given its adjacency lists.

## Sources
- TheAlgorithms/Python graphs/depth_first_search.py — non-recursive stack form; the push-all-neighbours variant and its mark-on-pop quirk; direct mapping lookup that fails on unknown nodes.
- TheAlgorithms/Python graphs/depth_first_search_2.py — recursive form over an adjacency dict; a failure mode (it iterates all vertices rather than the neighbours of the current node).
- TheAlgorithms/C-Plus-Plus graph/depth_first_search.cpp — recursive, mark on entry; O(V + E) and the list of applications (components, bridges, SCC).
- TheAlgorithms/C-Plus-Plus graph/depth_first_search_with_stack.cpp — explicit-stack form with colour states; same O(V + E).
- williamfiset/Algorithms DepthFirstSearchAdjacencyListRecursive.java — recursive reachable-node count; O(V + E) time, O(V) space.
- The `has_cycle` function is this entry's own addition, not taken from the sources (the C++ stack source only hints at colour states). The five sources agree on the core algorithm and O(V + E) time across three repositories; no conflict found. Two other pack files (a connected-components solver and two Ford-Fulkerson solvers) are DFS applications and were not used; a secondary notebook file only supplied the backtracking note.

## License Provenance
| repository | path | commit | license |
|---|---|---|---|
| TheAlgorithms/Python | graphs/depth_first_search.py | ef2ecc4d34d17ce6249ba5d3f3c17822dfd7bd50 | MIT |
| TheAlgorithms/Python | graphs/depth_first_search_2.py | ef2ecc4d34d17ce6249ba5d3f3c17822dfd7bd50 | MIT |
| TheAlgorithms/C-Plus-Plus | graph/depth_first_search.cpp | b64d5ecd022e4eb6b7f3f9a1157f13eccbfa6b78 | MIT |
| TheAlgorithms/C-Plus-Plus | graph/depth_first_search_with_stack.cpp | b64d5ecd022e4eb6b7f3f9a1157f13eccbfa6b78 | MIT |
| williamfiset/Algorithms | src/main/java/com/williamfiset/algorithms/graphtheory/DepthFirstSearchAdjacencyListRecursive.java | 08c6d5f3cbee6870f480272404a271cc003b7437 | MIT |
