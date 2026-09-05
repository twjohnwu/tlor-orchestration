# resume-protocol.md — Resuming a finished subagent by ID

Two cases. (1) A write-capable
producer blocked solely by plan mode, resumed after the user approves the
plan. (2) A read-only researcher blocked by an external human-pass gate
(CAPTCHA / anti-bot verifier) that reported the block per
agent_doc/noldor-browser.md and either left a Playwright browser open with
the challenge page visible, or handed off an ego-browser task space via
`handOffTaskSpace` — resumed after the user clears the gate (reclaiming an
ego task space with `takeOverTaskSpace`), same question, same scope,
browser session/task space untouched in between.
Never an external-system role (`palantir-stone`: a resumed context reuses
its pre-approval mutation enumeration — always a new dispatch with fresh
user confirmation), and §5 verification work always dispatches fresh. The
resume message is a full dispatch prompt (templates §2/§3 slots filled),
and its scope supersedes everything in the agent's earlier context — an
approved plan narrower than the agent's draft means the narrower scope,
nothing else. Dispatch fresh instead if approval widened or redirected the
scope (narrowing is the one survivable delta), if the agent's report
carried any STOP condition or unresolved question (case 2's bot-verifier
block itself is the one exception), or if you cannot
evidence that the agent's context and everything it worked with are
unchanged since it last ran (compaction on either side, workspace edits
during the pause, an unverified harness — each is "cannot evidence"). A
fix of verifier findings is never a resume — it is a fresh dispatch.
