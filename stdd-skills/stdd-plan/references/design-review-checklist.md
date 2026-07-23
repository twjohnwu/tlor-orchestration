# Design review checklist — mechanical vs. judgment

Distilled reference for `stdd-plan`'s pre-approval design review (S-08 gate,
step 7). Each item below is tagged **mechanical (→ /stdd-lint)** — checkable
without judgment, delegated to `/stdd-lint` — or **judgment (→ verifier)** —
requires reasoning about intent and quality, delegated to the fresh-context
verifier (`eagle-sentinel`) dispatched in step 7 before the coverage gate.

## Mechanical checks (→ /stdd-lint)

1. `design-be.md` / `design-fe.md` REQ/S-XX IDs ↔ `spec.md`
2. `api.yml` `operationId`/path ↔ `design-be.md`
3. `api.yml` field names ↔ `design-be.md` table schema (snake_case ↔
   camelCase mapping)
4. `design-fe.md` referenced endpoints ↔ `api.yml`
5. `design-be.md` Mermaid DB-operation notes ↔ table schema
6. `tasks.md` scenario ↔ `spec.md` coverage

## Judgment checks (→ verifier)

a. Every `REQ-XX`/`S-XX` in `spec.md` has a corresponding section in the
   design artifacts — no requirement silently dropped.
b. No invented requirement appears in the design that isn't traceable back
   to `spec.md` — the design does not scope-creep beyond the approved spec.
c. SOLID + DRY review, and GoF pattern-adoption reasonableness: a pattern is
   only justified by a repeated structure or a predictable point of
   variation (S-43) — not introduced as a quota or "because it's available".

The verifier judges each judgment item CONFIRMED or REFUTED per artifact;
REFUTED items go back to the producing step (design artifacts, step 4, or
tasks.md, step 6) for correction before the plan proceeds to the mechanical
checks and the approval gate (step 7).
