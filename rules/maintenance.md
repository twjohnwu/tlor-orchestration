---
description: Always-on guards for changing this rule system; the full maintenance protocol lives in agent_doc/maintenance.md.
managed-by: tlor-orchestration  # plugin-managed, do not edit; overrides go in rules/customize/
audience: all
version: 0.9.3
---

# maintenance.md — rule-system change guards (stub)

Before editing ANY rules / AGENTS.md / CLAUDE.md / memory file, read
`~/.claude/agent_doc/maintenance.md` first — it holds the full protocol
(lesson destinations, compaction triggers, file-retirement procedure,
invariants).

Always-on guards:
- Ask the user FIRST before: weakening any rule (MUST→MAY, raising retry
  caps, removing a verification step), deleting a rubric/template/reference
  file, restructuring the file layout, or changing the dispatch table or
  escalation thresholds. Stricter/more-accurate = self-serve; looser =
  user decision.
- Back up before rewriting any existing file (`cp X X.bak-YYYYMMDD`).
