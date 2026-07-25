# Reference: "Closing — decision capture (advisory)" (shared across stdd-explore/stdd-spec/stdd-uiux)

Single source of truth for the closing advisory step every stdd phase skill
(`stdd-explore`, `stdd-spec`, `stdd-uiux`) runs at the end of its own phase —
byte-identical across all three callers, so it lives here once (in
`stdd-spec`, the pipeline anchor) instead of being restated per skill.

## Closing — decision capture (advisory)

Before closing this phase, check whether it produced a decision that
passes the durability test (any of: changes a contract, schema,
architecture, or convention with future consequences; encodes a
non-obvious transferable lesson; guards against a plausible future
re-litigation of the same argument). If yes, ask the user with
AskUserQuestion — explicit options, never an open-ended question:
(a) archive to the project's decision log, (b) archive as a general
(cross-project) decision, (c) don't archive. If they pick an archive
option, invoke `/westmarch-scribe` with this phase's filled MADR /
decision material. This is a suggestion gate — never invoke the scribe
without the user choosing it.
