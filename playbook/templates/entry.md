---
id: <category.subcategory.name>
name: <Human name>
category: [<category>, <subcategory>]
confidence: high | medium
review_required: false
sources:
  - repo: <owner/name>
    path: <path/in/repo>
    commit: <40-hex>
    license: MIT
---

# <Human name>

## Problem Signals
<bullets: words in a task statement that point here>

## Use When
<bullets>

## Do Not Use When
<bullets — each names the alternative to use instead>

## Preconditions
<bullets — each one checkable before coding; violation = reject>

## Core Invariant
<one paragraph: the property the loop/recursion maintains>

## Algorithm
<numbered steps, language-neutral>

## Canonical Implementation
```python
<minimal, idiomatic Python, 3.7-compatible (`from __future__ import annotations`, no walrus, no `X | Y`); raises ValueError on a violated
precondition; no I/O; one public function>
```

## Complexity
Time: O(…) — why. Space: O(…) — why.

## Variants
<bullets: name — one-line delta from the canonical form>

## Common Failure Modes
<bullets — each phrased as a test you should write>

## Production Considerations
<bullets: recursion depth, overflow, stability, streaming, memory>

## Related Algorithms
<bullets: id — when you'd switch to it>

## Representative Problems
<bullets: generic problem statements, no site-specific titles>

## Sources
<bullets: repo path — what was taken from it (idea, edge case, variant)>

## License Provenance
| repository | path | commit | license |
|---|---|---|---|
