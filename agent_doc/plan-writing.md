# plan-writing.md — Plain-language rules for plans and dispatch prompts

Audience: the Maia (main-session orchestrator), loaded via the
`westron-plainspeech` skill before writing a final plan file or sending a
dispatch batch. Distilled from ISO 24495-1:2023 (plain language) and
ASD-STE100 Issue 9 (STE-flavored subset) — both are paid standards; this
file paraphrases publicly documented principles only, never verbatim text.
Deeper references: the plain-language core in
`~/.claude/agent_doc/bilbo-scribe.md`, the zh-TW plain-language layer in
`~/.claude/agent_doc/zh_tw/style.md`, and the STE modes in
`~/.claude/agent_doc/user-guide-ste.md`. This file adds the one calibration
none of them cover: planning artifacts.

## 1. Plan prose (zh-TW) — ISO 24495's four principles as plan checks

- **Relevant** — the Context section says why the change is being made, in
  ≤3 sentences the user recognizes as their own request.
- **Findable** — every phase has a one-line goal a scanning reader can
  find; headers name deliverables, not activities (「新增 X 檢核」, not
  「處理相關事宜」).
- **Understandable** — one read is enough: no term used before it is
  introduced; avoid 歐化長句、公文腔、成語堆疊 (zh_tw/style.md); technical
  tokens stay English, sentences stay Chinese.
- **Usable** — the user can act on the plan directly: every open decision
  is a named question, never an implicit assumption.

## 2. Dispatch prompts and acceptance criteria — STE-flavored

- One instruction per sentence.
- Procedure sentences ≤20 words; description sentences ≤25.
- Simple tenses ("run X; X returns Y"). Active voice for commands.
- No ambiguous pronouns — repeat the noun.
- Same term for the same thing across the whole batch (ubiquitous
  language): if the plan says "routing table", no prompt says "dispatch
  matrix".

## 3. Plan-specific checks (in neither upstream standard)

- Zero synonym drift between the plan's dispatch table and the actual
  dispatch prompts — same role names, phase names, file paths.
- Every acceptance criterion binds to something checkable: a command to
  run, a file:line to read, a count to compare. "Works correctly" is not
  a criterion.
- These checks complement dispatch.md §2's three-part contract and the
  delegation-templates slots; they never replace them.

## 4. Self-check before ExitPlanMode / before sending a dispatch batch

- [ ] Each phase goal findable in one line?
- [ ] Any sentence that needs a second read? Rewrite it.
- [ ] Any acceptance criterion without a runnable check?
- [ ] Any concept with two names across plan + prompts?
- [ ] Dispatch prompt sentences within the STE caps?
