# 實驗協定：單一 agent vs. TLOR 派工

[← 回 README](../../README.zh-TW.md)

本檔**只是實驗設計**。實驗尚未執行、沒有任何結果，執行需使用者另行核准
（見第 6 節執行閘）。任何人讀到本檔時若看見「結論」字樣，那也是待填的欄位，
不是既有發現。

## 1. 目的與假設

外部審閱指出：本專案至今沒有任何 outcome 證據，能說明 TLOR 派工紀律比
「一個 agent 自己做完」更好。本協定是缺的那份量測設計。

**受測主張（H1）**：在相同 orchestrator model 下，遵守 TLOR 派工紀律
（Arm B）相較單一 agent inline 執行（Arm A），在 outcome 指標上更好，
且 token 成本仍在可接受範圍。

可證偽形式，兩條同時成立才算支持 H1：

- **H1a（品質）**：Arm B 的 task success rate ≥ Arm A + 15 個百分點，
  或在 success rate 打平時，verifier findings 平均數 ≤ Arm A 的 70%。
- **H1b（成本）**：Arm B 的每題 total token 用量 ≤ Arm A 的 2.5 倍。

**推翻條件**：任一條不成立即視為 H1 未獲支持，且必須照實記錄
——「派工沒有比較好」是合法且有價值的結果，不得改判準來救結論。
既有 memory 已記錄 codex-first 首份實測為負節省，本實驗預期同樣可能為負。

## 2. 任務集

固定 24 題，六種形狀，兩臂共用同一份題目與同一份 acceptance criteria。

**Pinned-commit 規則**：每題綁定來源 repo 的一個 commit SHA，兩臂都在該
commit 的 detached worktree 上執行；跑完不 merge、不 push。設計當下三個
repo 的 HEAD 為 releaseGuard `7e8e746`、excelTemplateParser `9caee7a`、
mrinspect `117dafe`；正式執行前重新取一次 HEAD 並寫死進題目表，之後不再變。

| 形狀 | 題數 | 來源 repo | 寫入 |
|---|---|---|---|
| targeted lookup | 5 | 三 repo 皆有 | 否 |
| broad survey | 4 | releaseGuard / mrinspect | 否 |
| small implement | 4 | excelTemplateParser / mrinspect | 是 |
| mechanical batch | 3 | releaseGuard / excelTemplateParser | 是 |
| bug fix | 4 | 三 repo 皆有 | 是 |
| doc production | 4 | 三 repo 皆有 | 是（只寫 docs/） |

**完整 24 題題目表：待補**。選題規則（正式選題時逐條套用，選中與落選都記錄）：

1. 每題必須有一句可勾稽的 acceptance criterion，寫不出來就不收。
2. 唯讀題的答案必須能以 `file:line` 驗證；寫入題必須有可跑的驗證指令
   （`go test ./...`、`pytest`、`make build`）。
3. 三個 repo 的題數盡量平均，避免單一 codebase 主導結果。
4. 每種形狀的題目難度跨度要含至少一題「單檔可解」與一題「需跨 ≥3 檔」，
   以免形狀本身就決定了勝負（見第 7 節選題偏誤）。
5. 兩臂 prompt 逐字相同；題目敘述裡不得出現任何暗示派工的字眼。

### 具體題例（已寫好 acceptance criteria，兩臂共用）

**targeted lookup**

- L-01：在 mrinspect 找出 diff 預算裁切的實際上限值與套用位置。
  驗收：回報 `file:line` 與常數名，數值與該 commit 原始碼一致。
- L-02：在 releaseGuard 找出 GitLab client 重試次數的設定來源。
  驗收：回報 `file:line`，並指出該值是 hardcode 還是來自 config。

**broad survey**

- S-01：盤點 releaseGuard `internal/` 下所有對外 HTTP 呼叫點與其逾時設定。
  驗收：列出所有呼叫點 `file:line`；漏一處即 fail（以人工建立的 ground
  truth 清單比對）。
- S-02：盤點 mrinspect 的 error wrapping 慣例，指出不一致處。
  驗收：至少列出實際存在的兩種寫法各一例 `file:line`。

**small implement**

- I-01：excelTemplateParser backend 新增一個 `/healthz` 之外的就緒檢查端點，
  行為與既有 health 端點一致但額外回報 DB 可用性。
  驗收：`pytest` 綠；新端點有測試；不改既有端點行為。
- I-02：mrinspect 為某個既有 config 欄位加上範圍驗證。
  驗收：`go test ./...` 綠；含非法值的 table-driven 測試案例。

**mechanical batch**

- M-01：releaseGuard 指定 5 個檔案的 log 呼叫改為統一 helper。
  驗收：5 檔全數轉換；`go test ./...` 綠；行為零變更。
- M-02：excelTemplateParser 指定模組的 type hint 補齊。
  驗收：目標檔 mypy/ruff 無新增告警；`pytest` 綠。

**bug fix（必須 fail-then-pass）**

- B-01：在 pinned commit 上人工植入一個邊界條件 bug（off-by-one）並提供
  重現測試。驗收：修復前該測試 RED、修復後 GREEN，其餘測試不得由綠轉紅。
- B-02：植入一個 nil/None 解參考路徑。驗收條件同 B-01。
  （植入式 bug 的理由與風險見第 7 節。）

**doc production**

- D-01：為 releaseGuard 某個子系統寫一頁架構說明（繁中）。
  驗收：文中每個檔案路徑與指令都真實存在（verifier 逐一查證）；
  ≤120 行；不得出現該 commit 不存在的功能。
- D-02：把 mrinspect 某段 README 章節改寫為新手可讀版本。
  驗收：同 D-01 的路徑查證，且保留原有全部事實項目。

## 3. 兩臂協定

| 項目 | Arm A（單一 agent） | Arm B（TLOR） |
|---|---|---|
| orchestrator model | 同一個 model | 同一個 model |
| 派工 | **禁止**（不得使用 Agent/Task 工具） | 完整 TLOR 紀律（dispatch.md §1–§6） |
| 規則檔 | 極簡 CLAUDE.md：只有語言與 repo 慣例 | 完整 `~/.claude/rules/` + 12 角色 |
| 執行方式 | `claude -p`，每題全新 process | `claude -p`，每題全新 process |
| 工作區 | 寫入題用獨立 git worktree | 同左 |

其他一律相同：同一份題目 prompt（逐字）、同一個 pinned commit、同一台機器、
同一個 CC 版本、同樣不給網路以外的額外工具。**兩臂唯一的差異只有
「派工紀律 + 角色定義」這組規則**；任何其他差異都是實驗污染，發現即作廢重跑。

Arm A 的禁派工以兩層落實：(1) prompt 明文禁止；(2) hook 層攔截
Agent/Task 呼叫。只靠 prompt 不夠——規則層擋不住 harness 內建行為。

執行順序採交錯（A、B、A、B…）而非先跑完一臂，以攤平環境漂移。

## 4. 判定

判定者為**獨立 verifier（opus）**，每題一次 fresh session，只拿到兩樣東西：

1. 產出物（檔案 diff／回報文字，已剝除來源標記）
2. 該題的 acceptance criteria（與兩臂拿到的同一份）

**盲化做法**：

- 不提供任何 transcript、不提供派工紀錄、不提供 token 數字。
- 產出物一律轉存到同一個中性目錄（`arm-{1,2}/task-XX/`，編號與臂別的
  對應表由執行者保管，verifier 不得取得）。
- 回報文字先過一次機械式清洗：移除角色名（rohirrim/eagle/…）、移除
  「子代理」「派工」「dispatch」等字樣、移除 `[Agent]` 前綴。
- 清洗後由執行者以外的第二人（或第二個 session）抽檢 3 題，確認看不出臂別；
  抽檢失敗則該批全數重洗。

verifier 輸出格式：逐條 criterion PASS/FAIL + 證據（`file:line` 或指令輸出），
再列 findings（criteria 之外看到的問題，標 advisory）。verifier 不知道 H1。

## 5. 指標

| 指標 | 定義 | 量測方法 |
|---|---|---|
| task success rate | 該題全部 criteria 皆 PASS 的比例 | verifier 逐條判定，二值 |
| verifier findings | 每題 advisory findings 筆數 | verifier 報告計數，同一問題只計一次 |
| rework rounds | 產出物達到全 PASS 前，該臂自己重跑的輪數 | 逐次記錄，第一次即過為 0 |
| wall-clock | `claude -p` 程序啟動到結束的牆鐘秒數 | shell `time`，同機、同負載條件 |
| token usage | 該 session 全部 token（含子代理） | **erebor-ledger** 讀 CC transcript JSONL，依 `(message.id, requestId)` 去重後彙總 |
| dispatch error rate | Arm B 專屬：派工錯誤佔總派工數比例 | 人工分類：角色選錯、缺 acceptance criteria、被 dispatch_guard 擋下 |

token 量測前必須先確認當時 CC 版本的 transcript 欄位仍與 erebor-ledger 假設
相符；不符即停下，不得沿用舊格式硬算。三個模型層級的單價不同，成本一律
分模型列出，不做加權平均。

## 6. 成本估算與執行閘

粗估（僅為量級，不是承諾值）：

| 項目 | 每題估計 | 24 題小計 |
|---|---|---|
| Arm A | 60k–120k token | 約 1.5M–2.9M |
| Arm B | 150k–400k token（含子代理底盤，每 dispatch 約 33–46k） | 約 3.6M–9.6M |
| verifier（opus） | 30k–60k token | 約 0.7M–1.4M |
| 合計 | — | 約 5.8M–13.9M token |

牆鐘另估：24 題 × 2 臂 × 3–15 分鐘，加判定，約 3–8 小時。

**執行閘：本實驗不得在未取得使用者明確核准前開跑。** 核准內容須包含
token 預算上限與是否接受 N=1。

**N=1 警告**：初版每題每臂只跑一次。LLM 輸出有隨機性，單次結果無法區分
「派工有效」與「這次剛好比較好」。因此 N=1 版本只能產生**方向性訊號**，
不得寫成「已證實」。若方向性訊號顯著（H1a 差距 ≥ 15pp），再向使用者提案
挑 6–8 題做 N=3 複跑，並在複跑前先確認指標真的能分辨兩臂
——若第一輪兩臂分數全平，那是量測失效，該記錄的是工具限制而不是結論。

## 7. 效度威脅

- **Prompt 等價性**：兩臂拿到的題目字面相同，但 Arm B 的規則檔本身就是額外
  context，可能夾帶題目線索。緩解：規則檔內容凍結、不得為本實驗客製；
  正式跑前逐字 diff 兩臂的初始 context，只允許「派工紀律 + 角色定義」這一段
  不同，其餘不同處全部消除。
- **盲化洩漏**：Arm B 的產出物容易帶角色語氣、`file:line` 密度、報告結構等
  指紋，清洗規則抓不完。緩解：第 4 節的抽檢；殘留可辨識度須在結果中如實
  記載為已知限制，不得聲稱完全盲化。
- **選題偏誤**：題目若偏向「本來就適合拆」的形狀（broad survey、mechanical
  batch），Arm B 必勝；偏向單檔小改則 Arm A 必勝。緩解：六形狀固定配額、
  每形狀含單檔題與跨檔題；選題在看到任何結果之前定案並凍結，事後不得增刪。
- **植入式 bug 的人工痕跡**：B 系列的 bug 由人工植入，可能比真實 bug 更容易
  被定位。緩解：優先從 repo 的 git 歷史挑真實修過的 bug 還原成 pinned
  commit；真的找不到才植入，並在結果中標明哪幾題是植入的。
- **環境漂移**：跨數小時的執行期間，CC 版本、plugin 快照、機器負載、
  外部服務狀態都可能變動。緩解：交錯執行、全程不升級 CC 與 plugin、
  記錄每次執行的 CC 版本與開始時間；期間若發生任何升級，該批作廢重跑。
- **verifier 單點**：判定全由單一 opus verifier 決定，其偏好即為天花板。
  緩解：抽 4 題交第二位 verifier 複判，記錄兩者不一致率；不一致率高則
  該輪的品質指標不可採信。
