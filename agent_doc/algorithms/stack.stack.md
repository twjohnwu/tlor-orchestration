---
id: stack.stack
name: Stack
category: [stack]
confidence: high
review_required: false
sources:
  - repo: TheAlgorithms/Python
    path: data_structures/stacks/balanced_parentheses.py
    commit: ef2ecc4d34d17ce6249ba5d3f3c17822dfd7bd50
    license: MIT
  - repo: TheAlgorithms/Python
    path: data_structures/stacks/stack.py
    commit: ef2ecc4d34d17ce6249ba5d3f3c17822dfd7bd50
    license: MIT
  - repo: TheAlgorithms/Python
    path: data_structures/stacks/postfix_evaluation.py
    commit: ef2ecc4d34d17ce6249ba5d3f3c17822dfd7bd50
    license: MIT
  - repo: TheAlgorithms/C-Plus-Plus
    path: data_structures/stack.hpp
    commit: b64d5ecd022e4eb6b7f3f9a1157f13eccbfa6b78
    license: MIT
  - repo: williamfiset/Algorithms
    path: src/main/java/com/williamfiset/algorithms/datastructures/stack/Stack.java
    commit: 08c6d5f3cbee6870f480272404a271cc003b7437
    license: MIT
  - repo: williamfiset/Algorithms
    path: src/main/java/com/williamfiset/algorithms/datastructures/stack/IntStack.java
    commit: 08c6d5f3cbee6870f480272404a271cc003b7437
    license: MIT
---

# Stack

## Problem Signals
- balanced or matching brackets, parentheses, braces
- most recently opened item must be closed first
- evaluate a postfix (reverse Polish) expression
- undo, backtrack, or "last in, first out" order
- nested structure processed innermost-first
- replace recursion with an explicit work list

## Use When
- Items must be handled in the reverse order they were seen, and only the newest unresolved item matters at any step.
- You scan a sequence once and each closer must pair with the latest unmatched opener.
- An expression in postfix form must be reduced operand by operand.
- A recursive traversal risks exceeding the recursion limit and can be turned into an explicit loop.

## Do Not Use When
- Items must come out in arrival order: use a queue (`collections.deque`).
- You need the next greater or smaller element for every position: use `stack.monotonic_stack`.
- You need the smallest or largest pending item: use a heap.
- You need the shortest path or fewest steps in a graph: use `graph.traversal.bfs`.
- Random access to arbitrary middle items is required: use a plain list or dict.

## Preconditions
- The input is a string that can be consumed in one left-to-right pass; reject other types.
- Every opener has a known, fixed closer (a closed mapping such as `(`/`)`, `[`/`]`, `{`/`}`).
- Characters outside the mapping are either ignored or rejected by a rule fixed up front, not decided per case.
- Pop and peek are only issued on a non-empty stack; check emptiness first.

## Core Invariant
After reading any prefix, the stack holds exactly the openers that are still unmatched, oldest at the bottom and newest on top. A closer is valid only if it matches the top; a prefix with a closer on an empty stack, or with a top that does not pair, can never be completed into a balanced string, so the scan stops with failure. The whole string is balanced when the stack is empty at the end.

## Algorithm
1. Reject input that is not a string.
2. Build a map from each closer to its opener.
3. Create an empty stack (a list; append to push, pop from the end).
4. For each character: if it is an opener, push it; if it is a closer, fail when the stack is empty or its top is not the matching opener, else pop; otherwise skip it.
5. After the last character, return true only if the stack is empty.

## Canonical Implementation
```python
from __future__ import annotations

from typing import List

_PAIRS = {")": "(", "]": "[", "}": "{"}
_OPENERS = frozenset(_PAIRS.values())


def is_balanced(text: str) -> bool:
    """Return True if every bracket in text is closed by its match, in order.

    Characters other than the three bracket pairs are ignored.
    """
    if not isinstance(text, str):
        raise ValueError("text must be a str, got %s" % type(text).__name__)
    pending: List[str] = []
    for ch in text:
        if ch in _OPENERS:
            pending.append(ch)
        elif ch in _PAIRS:
            # A closer needs a pending opener, and it must be the newest one.
            if not pending or pending.pop() != _PAIRS[ch]:
                return False
    return not pending
```

## Complexity
Time: O(n) — each character is examined once and push/pop at the end of a list are O(1) amortized. Space: O(n) — the stack holds up to n openers (a string of only openers).

## Variants
- Stack class — wraps the list with push, pop, peek, size, is_empty; pop and peek on empty raise a dedicated error (Python, C++ and Java sources all do this).
- Bounded stack — a fixed limit that rejects a push when full (Python `Stack(limit)`, Java `IntStack(maxSize)`); trades flexibility for a known memory cap.
- Linked-list stack — head node is the top; push and pop rewire the head, giving O(1) worst case with no resizing (C++ `stack.hpp`).
- Array-backed stack — a preallocated array plus a top index; no per-item allocation (Java `IntStack`).
- Postfix evaluation — push numbers; on an operator pop two operands (right one first), push the result; exactly one value must remain. A unary sign needs a special case when fewer than two values are present (Python `postfix_evaluation.py`).
- Bracket kinds as data — extend the closer map to support more pairs without changing the loop.

## Common Failure Modes
- Test a closer on an empty stack, such as `")"`, returns False and does not raise.
- Test leftover openers, such as `"(("`, returns False even though no mismatch was seen.
- Test crossed pairs, such as `"[(])"`, returns False; counting each kind separately would wrongly accept it.
- Test deep nesting (more than ten openers) still works; the Python source's `Stack()` default limit of 10 would raise on the eleventh push.
- Test the empty string and a string with no brackets return True.
- Test popping or peeking an empty stack in the Stack variant raises your chosen error, not an `IndexError` from the list.
- Test postfix with operand order: `"4 2 -"` is 2, not -2.

## Production Considerations
- A list used as a stack grows as needed; do not use `list.pop(0)` or `insert(0, x)`, which are O(n).
- For multithreaded use, `queue.LifoQueue` provides locking; a plain list is not guarded.
- A bound on depth protects against hostile input in untrusted parsers; the bound should raise a clear error, not an exotic base exception.
- Streaming works naturally: the state is just the stack, so you can feed chunks and check at the end.
- Replacing recursion with a stack avoids the interpreter recursion limit; it does not reduce memory.

## Related Algorithms
- `stack.monotonic_stack` — when the question is the nearest greater or smaller item per position.
- `graph.traversal.dfs` — a depth-first traversal is a stack of pending nodes; switch to it for graph reachability.

## Representative Problems
- Decide whether a string of mixed brackets is correctly nested.
- Evaluate an arithmetic expression given in postfix notation.
- Simulate an undo history that reverts the latest action first.
- Convert a recursive tree walk into an iterative one.
- Find the length of the longest well-formed bracket substring.

## Sources
- TheAlgorithms/Python data_structures/stacks/balanced_parentheses.py — bracket-matching loop with a closer-to-opener map; closer on empty stack fails; final emptiness check.
- TheAlgorithms/Python data_structures/stacks/stack.py — Stack class with limit; underflow on empty pop and peek; the default limit of 10 would break deep nesting in the bracket check (failure mode).
- TheAlgorithms/Python data_structures/stacks/postfix_evaluation.py — postfix reduction, operand order, unary sign edge case, single-result check (variant).
- TheAlgorithms/C-Plus-Plus data_structures/stack.hpp — linked-list stack with empty-checked pop and top (variant).
- williamfiset/Algorithms .../stack/Stack.java — the interface: size, is_empty, push, pop, peek; pop and peek on empty raise.
- williamfiset/Algorithms .../stack/IntStack.java — fixed-capacity array stack and its trade-off (variant).
- All sources agree on LIFO semantics, O(1) push/pop/peek, and error-on-empty; no conflicts found. The two other C++ array/linked-list files and the Java list/array stacks were skipped as boilerplate repeats of the same operations.

## License Provenance
| repository | path | commit | license |
|---|---|---|---|
| TheAlgorithms/Python | data_structures/stacks/balanced_parentheses.py | ef2ecc4d34d17ce6249ba5d3f3c17822dfd7bd50 | MIT |
| TheAlgorithms/Python | data_structures/stacks/stack.py | ef2ecc4d34d17ce6249ba5d3f3c17822dfd7bd50 | MIT |
| TheAlgorithms/Python | data_structures/stacks/postfix_evaluation.py | ef2ecc4d34d17ce6249ba5d3f3c17822dfd7bd50 | MIT |
| TheAlgorithms/C-Plus-Plus | data_structures/stack.hpp | b64d5ecd022e4eb6b7f3f9a1157f13eccbfa6b78 | MIT |
| williamfiset/Algorithms | src/main/java/com/williamfiset/algorithms/datastructures/stack/Stack.java | 08c6d5f3cbee6870f480272404a271cc003b7437 | MIT |
| williamfiset/Algorithms | src/main/java/com/williamfiset/algorithms/datastructures/stack/IntStack.java | 08c6d5f3cbee6870f480272404a271cc003b7437 | MIT |
