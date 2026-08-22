# palantir-protocol.md — Mandatory dispatch protocol for palantir-stone

Audience: the Maia (dispatcher). Read this BEFORE composing any
`palantir-stone` dispatch — the role's tools are MCP-only (no file Read),
so this protocol binds the DISPATCH PROMPT, not the agent's own reading.
Moved out of the dispatch.md §3 table cell 2026-08-22; content unchanged.

## T1 gate (always)

Outward-facing writes are risk-tiers T1: the Maia MUST obtain the user's
explicit confirmation of the exact mutation enumeration BEFORE dispatching.
Approval is per-dispatch. Never resume a palantir-stone agent — a resumed
context reuses its pre-approval mutation enumeration; always a new dispatch
with fresh user confirmation (dispatch.md §4).

## Update dispatches

- The dispatch MUST enumerate every mutation: target gid + title,
  expected-before, literal new value.
- Max 10 update mutations per dispatch.

## Create dispatches

- Each create item carries: the service; a literal `operation: create`
  marker; container gid + name; the literal task name; every literal field
  value (or "no other fields"); `expected: absent`.
- Max 25 create items per dispatch (updates stay 10).
- Create and update never mix in one dispatch.

## Retry dispatches

- A RETRY dispatch marks each retried create item
  `retry-of: <gid | none (stopped pre-write) | unknown (create call ran,
  no gid)>`.
- Each retried comment is marked
  `retry-of: comment (prior outcome <label>)`.
- This per-item syntax is stricter than, and separate from, the general
  one-line `retry-of:` marker in delegation-templates.md.
