# Skills

[← 回 README](../../README.zh-TW.md)

快速參考見 README 的 skill 路由表。本頁補充該表以外的細節，以及 STDD 選配安裝的說明。

## 自動載入 skills——細節

**rivendell-council** — 抗辯小組的召集流程：組裝自足審查包、並行派遣三鏡頭、以多數存活制判定、關鍵結論循環至收斂。

**tlor-init** — 一次性設定 skill：選安裝層級（使用者層/專案層/repo 層）、複製 agents 與 rules、產生 CLAUDE.md 路由與 AGENTS.md、選配啟用 hooks。
偵測既有安裝並提供帶備份的升級流程。也提供選配的 STDD 安裝步驟（見下）。

**tlor-restore** — 從 `/tlor-init` 升級時建立的備份還原。

**erebor-ledger** — 讀取既有的 Claude Code transcript，回報 tlor 角色派工相較於直接在 orchestrator 模型上跑同樣工作省下多少成本。僅回溯性報表，不是單次進行中派工的即時估算工具。

**westron-plainspeech**——計畫工件的平語化檢核:plan 散文套 ISO 24495 四原則,dispatch prompt 與 acceptance criteria 套 STE 式句長/術語檢核。
清單本體在 `agent_doc/plan-writing.md`,skill 只是讀取它的薄觸發殼;由 dispatch.md 的 plan-mode requirements 在寫最終 plan 檔前指名。

### `disable-model-invocation: true` 這個旗標實際的效果

`tlor-init` 與 `tlor-restore` 的 frontmatter 都設了 `disable-model-invocation: true`。設了這個旗標的 skill，模型完全看不到，所以在 CLAUDE.md、AGENTS.md 或任何 rules 檔裡寫指示都無法啟用它：讀那些指示的模型，手上根本沒有這個 skill 可以呼叫。只有兩條路徑能啟動它，一是使用者自己打 `/skill-name`，二是該 plugin 自己的 SessionStart hook。所以排流程時要算進去：用到這兩個 skill 的設定步驟只能由使用者親自跑，agent 代不了。

### 觸發方式

`/rivendell-council` 的自動叫用是由 description 驅動的——模型會拿 skill description 裡的觸發詞去比對當下情境。若要硬保證觸發，在你專案的 `CLAUDE.md` 加一行：

```
High-risk verdicts (irreversible ops, contract/schema changes, money/precision, architecture decisions, root-cause claims, production-affecting conclusions) MUST pass /tlor:rivendell-council before adoption.
```

`eagle-sentinel` 給出 HIGH-RISK 建議就是該召集的訊號。

## 選配：STDD 工作流程 skills

透過 `install.sh --stdd-role=ALL` 或 `/tlor-init` 的 STDD 步驟安裝。

這九個 skill 不會自動載入，只有你明確要求時才會安裝到 `~/.claude/skills/`。其中七個實作 Spec-driven Test-Driven Development 流程，另外兩個負責決策紀錄的歸檔與查詢。

本輪只出 `ALL` 這一個 profile。`RD`／`PM`／`UIUX` 角色限定子集 deferred，`install.sh --stdd-role=RD|PM|UIUX` 只會印出 deferred 訊息，不安裝任何東西。

| Skill | 中土稱號 | 用途 | 何時呼叫 |
|---|---|---|---|
| `/stdd` | Palantír 真知晶石 | 唯讀狀態儀表板：回報這個 STDD 變更目前在哪個階段、重新驗證 fingerprint、建議下一步指令 | 檢查進行中 STDD 變更的進度 |
| `/stdd-explore` | Lore 智者探詢 | 在寫任何 spec 之前，先釐清模糊需求的思考夥伴階段 | 從一個粗略想法開始新的 STDD 變更 |
| `/stdd-uiux` | Lórien 精靈美學 | 條件式設計階段，產生 `design-ux.md` | 僅當變更有使用者可見的 UI 介面時 |
| `/stdd-spec` | Oath 遠征誓約 | 撰寫 GWT 格式 `spec.md`（含 test-mapping/verification-command 欄位）、以 `/stdd-lint` 自我複查、並以抗辯小組核准作為關卡 | 撰寫或核准某個 STDD 變更的 spec |
| `/stdd-plan` | Map 行軍圖 | 從已核准的 spec 產生條件式的 `design-be.md`/`design-fe.md`/`api.yml` 與涵蓋所有情境的 `tasks.md` | 把已核准的 spec 轉成設計與任務清單 |
| `/stdd-execute` | Forge 鑄造 | 對已核准的 `tasks.md` 逐任務跑 RED → GREEN → REFACTOR 迴圈，雙派工模型＋獨立驗證者 | 逐一實作 STDD 任務 |
| `/stdd-lint` | Eagle Vision 鷹之視野 | 純規則式（非模型判斷）機械檢查：佔位字串洩漏、ID 連續性、GWT 完整性、test-mapping/涵蓋率、fingerprint 狀態 | 由 stdd-spec/stdd-plan/stdd-execute 的邊界檢查內部呼叫，使用者也可直接呼叫 |
| `/westmarch-scribe` | Westmarch 記事錄 | 決策歸檔：把已填 Outcome 的精簡 MADR 決策寫入專案 decision log（或 instruction 檔、通用決策紀錄） | 由 stdd-explore/stdd-uiux/stdd-spec/stdd-plan 的建議性收尾步驟呼叫，使用者也可直接呼叫，或對話中出現決策關鍵詞時主動觸發 |
| `/minas-tirith-archivist` | Minas Tirith 檔案守護者 | 決策查詢：`/westmarch-scribe` 的唯讀對應版，搜尋已歸檔的決策紀錄（通用與專案層級）並附引用回答，絕不寫入或編輯 | 詢問過去的決策或某個慣例的緣由，或使用者直接呼叫 |

`/westmarch-scribe` 與 `/minas-tirith-archivist` 都要有 tlor rules 層才會動，判斷方式是找 `dispatch.md` 與 `judgment.md` 在不在。找不到，兩者都直接**停止**並回報「tlor rules not installed — run `/tlor-init` first」，不會自己猜要寫到哪或搜哪裡。

流程順序：`stdd-explore → stdd-uiux（條件式）→ stdd-spec → stdd-plan → stdd-execute`，`stdd` 與 `stdd-lint` 則任何階段都可呼叫。

### BDD 層（v0.12.0）

以下五項疊在上面那串階段之上，沒有新增任何階段：兩項是條件式產出，一項是寫進 execute 派工提示裡的判準，兩項是你可以跑的檢查。

- `stdd-explore` 在交棒前先做一份 Example Map，條件是這次變更牽涉商業規則、狀態，或一個以上的條件互相牽動。這份 map 分四層：一句話的 Story、一條規則一行的 Rules、每條規則至少一個具體的 Examples，以及盤點過程中冒出來、還沒有答案的 Open Questions。純基礎設施變更（相依升版、CI 設定、不動行為的重構）整步跳過。
- `stdd-spec` 在 `spec.md` 補一節 `## Domain Language`，條件是這次變更引入新的領域術語，或同一個詞在產品、程式碼、測試、文件之間意思已經對不起來。那節就是一張表：術語、確切意思、不准拿來替代它的同義詞。
- `stdd-execute` 要求 builder 與 verifier 都把 THEN 讀成外部可觀察的行為——狀態、輸出、時間表現。只點名內部呼叫的 THEN 要標出來，因為那鎖住的是實作，不是行為。
- `stdd-lint` 的 Check 16 檢查 test mapping 存不存在：逐一確認情境指到的檔案在磁碟上找得到，且指到的函式名字出現在那個檔案裡面。嚴重度看階段：`tasks.md` 裡該情境的任務還沒打勾時報 WARN，因為測試檔是 RED 步驟才寫的，那之前本來就該不存在；任務一旦標成 `[x]` 就改報 FAIL。
- `scripts/stdd_verify.py` 把各情境當成一組跑完：執行每個情境的 verification command，印出逐情境的 PASS/FAIL/MISSING 表格，再加一行涵蓋率。MISSING 指的是 verification command 缺漏，或 `Test mapping` 指的測試檔不在。所有被選中的情境都 PASS，exit code 才會是 0。

**STDD test-file guard hook**（`hooks/stdd_test_guard.py`）——選配的 PreToolUse hook。測試檔一旦建立 RED baseline，在它的任務標記完成之前，這個 hook 會擋掉對它的改寫。用 `install.sh --install-hook` 安裝，與 `--stdd-role` 無關。
**session-snapshot 誠實提醒**：Claude Code 只在 session 啟動時讀一次 `settings.json` 裡的 PreToolUse hook。在既有 session、或 `--continue`／`--resume` 起來的 session 中執行 `--install-hook`，該 hook 在那個 session 不會生效。請只在全新 session 中驗證。
