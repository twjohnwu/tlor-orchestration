---
name: westron-plainspeech
description: Plain-language pass for planning artifacts — use when writing or reviewing a plan file, and before sending a batch of dispatch prompts. Applies ISO 24495 principles to plan prose and an STE-flavored checklist to dispatch prompts and acceptance criteria. Triggers: "plain-language plan", "平語化計畫", plan-mode final write-up (named by rules/dispatch.md's Plan mode requirements).
---

# Westron Plainspeech (通用語 — plain language for plans)

Westron is Middle-earth's Common Speech — what every reader actually
understands.

1. Read `~/.claude/agent_doc/plan-writing.md` and apply its checks to the
   artifact at hand: §1 for plan prose, §2 for dispatch prompts and
   acceptance criteria, §3 and §4 always.
2. If that file is missing, run only this degraded check and say so
   plainly: every phase has a one-line goal; every acceptance criterion
   names a runnable check; one term per concept. Do not reconstruct the
   full checklist from memory.
3. Report what you changed or flagged. Do not certify your own plan as
   clear — the reader's read is the verdict.
