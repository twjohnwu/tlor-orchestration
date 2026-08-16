# STDD review：statusline 重寫

[← 回到 README](../../../README.zh-TW.md)

寫於 2026-08-15。

STDD（spec-test-driven development）是此 workspace 為高風險變更提供的選配
pipeline：`explore → uiux → spec → plan → execute`；其中有 spec gate 的對抗式
審查小組、fingerprint 鎖定的產物、每個任務各自的 RED → GREEN → REFACTOR
迴圈，以及對每個交付物進行獨立 fresh-context 驗證。這個 framework 現已
dogfood 過兩次，兩次都是 *replacement-type* 專案，驗收門檻皆為「行為必須
與前身完全一致」：

- **D1** — `coralline` → `phosphorflux`：Claude Code statusline tool 的
  TypeScript 重寫（2026-07-30 to 08-03）。
  已發布的 audit trail：[phosphorflux `docs/tlor-stdd/`](https://github.com/twjohnwu/phosphorflux/tree/main/docs/tlor-stdd)。
- **D2** — `phosphorflux` → `phosphorpulse`：同一個 tool 的 Rust 重寫
  （位元組級一致(byte-parity)的 renderer，接著是整合 Codex CLI 的全螢幕 TUI；2026-08-14/15）。
  已發布的 audit trail：[phosphorpulse `docs/tlor-stdd/`](https://github.com/twjohnwu/phosphorpulse/tree/main/docs/tlor-stdd)。

本報告比較兩次執行：各 pipeline stage 的 token 支出、兩次執行揭露的返工
模式、其間及期間 framework 修正的內容，以及仍待處理的事項。

## 1. 規模與輪次

| | D1（TS 重寫） | D2a（Rust renderer） | D2b（Rust TUI） |
|---|---|---|---|
| Requirements / 情境(scenario) | 11 / 27 | 9 / 17 | 9 / 17 |
| Tasks | 39 items（收斂為 8 TDD + 4 INFRA） | 12 | 12 |
| Spec panel verdicts | 11/11 REFUTED → revised | several REFUTED（包括一個本會讓整個 execute phase 失效的黃金樣本的非決定性(golden-nondeterminism)問題） | several REFUTED in v1（例如一個融合的 TextMate-scope 設計缺陷） |
| Fix rounds inside execute | 6 rounds，跨 4 個 tasks（每個 task 最多 2 次） | 一個 task 有 5 rounds（單一最昂貴點） | 3 次經核准的 single-round fixes |
| Post-execute 走查(walkthrough) | 8 個 patch releases，8 個 failure classes | 8 個 review rounds | 14 個 review rounds + 9 個使用者驅動走查輪次 |

## 2. Token 核算

**兩次執行的 metrics 不同——請先閱讀此 caveat。** D1 的 ledger 記錄
*output tokens*（多數工作經由 workflow fan-out 執行）。D2 記錄
*per-dispatch total context*（`subagent_tokens`）。各欄無法彼此相除；重要的是
欄內結構。

### D1（~2.07M output tokens，≈$185 API-equivalent）

| Component | Amount |
|---|---|
| Main dialogue | 186,897 output tokens |
| Role dispatches ×41 | ~308k |
| Workflow agents（9 runs，3,672 records） | ~1.58M |

Execute 約占 dispatch usage 的 ~89%。記錄的浪費：一輪 scaffold-race 在 86 個
agents 間燒掉 6.4M tokens；一次 rate-limit wipeout 讓 21 個 agents 損失
1.68M；每個 agent 重讀 spec 造成 223.6M 累積 cache-read tokens。

### D2a — Rust renderer（61 dispatches，~3.46M subagent tokens）

| Pipeline stage | Agents | Count | Tokens |
|---|---|---:|---:|
| explore | search + Rust spike | 2 | 131k |
| spec panel | 3 adversarial lenses（opus） | 3 | 279k |
| plan verification | verifier ×2 | 2 | 126k |
| execute（RED/GREEN/fix） | 透過 agent wrapper 的 Codex | 26 | 1,292k |
| execute verification | fresh-context verifier | 12 | 681k |
| review closeout | 8 review/fix rounds | 10 | 494k |
| TUI pre-work（explore/spec） | search/research/panel | 6 | 452k |
| **Total** | | **61** | **≈3,455k** |

最糟的單一點：一個 task 消耗 7 dispatches = 405k（GREEN + 5 fix rounds +
verification）；其中約 ~150k 本可藉由將已知陷阱（例如剛寫入的 stubs 在 macOS
上的 first-exec latency）預先載入 RED prompt 而避免——而這正是 dispatch
checklist rule 現在做的事。根因量測：*每個* subagent 都帶著約 ~33k 的固定
context floor（其中約 ~21k 是 auto-loaded rules corpus）；Codex CLI 外的 agent
wrapper 又加了 ~13k，因此無論 task 大小，每次 builder dispatch 的 floor 都是
46,428-token。

### D2b — TUI（+9 走查輪次，~2.33M subagent tokens）

| Stage | Direct Codex CLI calls | Claude dispatches | Tokens |
|---|---:|---:|---:|
| execute T1–T12 builders | ~26 | 0 | ≈0 |
| execute verification | — | 14 | ~925k |
| review（14 rounds + 13 fix rounds） | ~27 | 1 | ~69k |
| documentation（bilingual README/guides） | ~4 | 5 | ~300k |
| 走查修正（9 rounds） | ~22 | 0 | ≈0 |
| 走查驗證 + research | — | 12 | ~880k |
| framework maintenance | — | 3 | ~156k |
| **Total** | **~79** | **35** | **≈2.33M** |

cost-reduction plan 在 D2a 與 D2b 之間落地：以直接 CLI invocation 取代 agent
wrapper，將 builder 端從每 dispatch ~46k 降到 ~0——估計在 ~79 calls 上節省
2.8–3.6M。成本中心整個移至 verification：27 次 verifier dispatches ≈1.87M
（~81%）；隨著 fingerprint ledgers 與 criteria 在 prompts 中累積，每輪成本從
54k 成長至 90–104k。

## 3. 兩次執行共同的返工模式

1. **Parity 細節會在 execute 後才浮現——除非已有判準(oracle)。** D1 最昂貴的
   教訓：前身全程皆可執行，卻直到多輪人工目視後才建立黃金樣本比對(golden diff)判準。
   D2a 採用黃金樣本優先，其 renderer 需要 *zero* 走查輪次——17 個
   情境在首次使用者接觸時便通過。D2b 的九輪走查全落在沒有
   判準的表面（TUI visuals、keybindings、i18n）。經驗法則：
   **走查輪次 ≈ 無判準的表面積**。
2. **若任由它們自行認證，tests 就會認證自己。** D1：一個 synthetic fixture
   在同一個 field 三次產生 false greens。D2：一個 test 將 implementation 與
   自身比較（compile-time tautology），另一個把錯誤的 move semantics 編成
   expectation。Green tests 對 parity 證明不了什麼；只有 fresh-context review
   對照獨立判準（frozen predecessor 的 source）才能抓到這些問題。
3. **Prose 禁令擋不住機械式違規。** 即使每份 prompt 都有明確禁令，D2 中
   repo-wide formatter sweep 仍穿透三次獨立 dispatches。持久的修正是 script，
   不是更強的文字：任何 verifier dispatch 前現在都會執行 mechanical-check
   script（fingerprint ledger、test counts、tracked-file allowlist、spec
   fingerprints——每項一行 PASS/FAIL 加上一份 debug log）。
4. **每次修正後成本中心都會遷移。** D1 由 workflow fan-out races 主導；D2a
   由 wrapper 的 fixed floor 主導；D2b——builder 降至 ~0 後——由 verification
   主導。每個排除的瓶頸都會暴露下一個；當前的是 verifier dispatches 下的固定
   context floor，以及混進 judgment work 的 mechanical checks。

## 4. 已落地的 framework 改進

| Improvement | Origin | Status |
|---|---|---|
| Test-file fingerprint firewall（sha256 經 prompts 傳遞，不經 files） | D1 | 全程於 D2 強制；抓到一次真實違規與三次 formatter leaks |
| 適用 replacement-type changes 的黃金樣本/判準優先 | D1 lesson | 在 D2a 驗證（zero renderer 走查輪次） |
| Dispatch checklist（10 條 field-proven clauses：stub warm-up、piped stdio、sandbox limits、regression attribution、…） | 從 D2a 的 5-round rework 提煉 | 全程套用於 D2b |
| 供 builders 使用的 Direct CLI invocation（繞過 ~46k/dispatch agent wrapper） | D2a measurement | 用於 D2b 全部；兩個 invocation pitfalls（write-mode flag、shell quoting）回饋至 recipe |
| Sanctioned-fix procedure（經授權的 locked-test amendments，附 re-baselined fingerprints） | D2a | used 4 times in D2b，每次皆有 evidence 與 re-verification |
| 鏡像 reference implementation 時強制 source-line citations | D2b 第 3 輪走查 | builders 不得憑記憶重塑 UI layers |
| Mechanical-check script（fingerprints / test counts / scope allowlist / spec hashes） | D2b | 以 fail-then-pass validation 落地 |

## 5. 建議與待辦事項

1. **在 pipeline 內產生 mechanical-check script**（approved direction）：一旦
   RED 完成且 orchestrator 持有 test fingerprints，就發出／更新每個 change 的
   script（ledger、各 task 附 expected counts 的 verification commands、scope
   allowlist、spec hashes；PASS/FAIL + debug log）。在每次 GREEN/fix/verify 前
   執行；verifiers 只保留 judgment work。預期：每個 verification round 節省
   15–25k，並立即攔截 formatter-leak-class violations。
2. **將走查正式化為 pipeline stage。** 兩次執行皆證明，對於
   replacement-type changes，「execute complete」≠「acceptable」：D1 需要 8 個
   patch releases，D2b 需要 9 rounds。將
   report → adjudicate-against-oracle → batched-fix → mechanical-check →
   verify loop 做成 completion gate 與 manual checklist 之間的明確 stage，並在
   plan time 為帶有 UI 的 changes 編列其 rounds 預算。
3. **供 UI changes 使用的 screen-mapping artifact。** Design prose 無法約束 UI
   layer；一張 plan-stage table（每個 screen：reference implementation
   file:line ↔ new file ↔ keybinding/visual invariants）供 builder prompts 與
   verifier checks 使用，可能會省下 D2b 九輪中的 3–4 輪。
4. **縮減 per-dispatch context floor**（open decision）：選項包括為 subagents
   條件式載入 rules、corpus distillation，或每角色選擇退出 inheritance。在
   D2b 的 35 Claude dispatches 下，完全實現能為每個 change 節省 ≈700k。
5. **將判準優先普遍化**：「一個 replacement-type change 必須在其第一個
   task 之前擁有可執行的判準（黃金樣本比對或 screen mapping）」應納入
   plan-stage design checklist——D1 已為此付費，D2a 已驗證。

## 方法論

數字來自三個來源：phosphorflux audit trail 中 D1 的已 commit ledgers；D2 的
per-dispatch harness telemetry（`subagent_tokens`、exact values）；以及從
session record 統計的 direct-call counts（±3）。所有 figures 在發布前皆由
fresh-context reviewer 對照 primary sources 重新驗證；它抓到的兩個 errors
（一個情境數與一個 percentage）已修正。兩次執行的 metrics
刻意不合併為單一 total，因為其 units 不同。
