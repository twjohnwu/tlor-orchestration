# Rules 與 Hooks

[← 回 README](../../README.zh-TW.md)

## Rules

本 plugin 附帶去個人化的編排規則，用 `/tlor-init` 或 `install.sh` 安裝：

**必裝**（6 檔，由 plugin 擁有——每次安裝／升級皆無條件覆蓋，`version`
由 `.claude-plugin/plugin.json` 蓋上，不含 `## Lessons` 區塊——見
[installation.md](installation.md) 的所有權模型）：

| Rule | 用途 |
|---|---|
| `dispatch.md` | 角色派工表、委派合約、升降級路徑、驗證規則 |
| `decomposition.md` | 如何拆解任務（並行/序列、規模限制）|
| `delegation-templates.md` | 各派工類型的填空提示模板 |
| `judgment.md` | 何時升級、何時完成、何時問人、錯方向訊號 |
| `risk-tiers.md` | 行動風險分級（T1 不可逆 / T2 難復原 / T3 可逆）|
| `maintenance.md` | session 可自行修改 vs 需人類核准的項目 |

**選裝**（6 檔，位於 `rules/customize/`——`--with-optional` 或在
`/tlor-init` 中選擇；一旦複製過去就不會再被覆蓋）：

| Rule | 用途 |
|---|---|
| `design-principles.md` | 7 個未覆蓋情境的備用原則（P1-P7）|
| `user-decision-patterns.md` | 3 個 AI 輔助開發的決策模式（D1-D3）|
| `judgment.md` | 精簡 MADR 候選比較格式＋累積跨專案決策的「General decisions log」（base `judgment.md` §5 指向此檔）|
| `letter-to-future-sessions.md` | 空白模板——逐次填入專案事實、制度衰退對策、誠實的能力邊界 |
| `skill-triggers.md` | 何時該呼叫 skill，而非照單全收「一律呼叫」的注入規則——需自行填入已裝 plugin 的 namespace 優先序 |
| `lessons.md` | 附加式的反覆工作流失敗紀錄，每個 base rule 檔案各一個區塊 |

你也可以把自己團隊的規則檔（`.md`）直接放進 `rules/customize/`：安裝時會一併
複製，installer 永遠不會動它。它們會原生自動載入，跟這裡其他檔案一樣走
`.claude/rules/` 機制，不需要路由表。`/tlor-init` 產生的路由表只是幫那些不懂
`.claude/rules/`、只讀 AGENTS.md 的工具記下這個目錄，不是它讓檔案載入的。

## Agent docs（agent_doc/，懶載入）

角色專屬、條件觸發的參考文件。被派工的 subagent 只在觸發條件成立時才
Read（機器上有 codex、頁面只有 JS 殼、判定進入 HIGH-RISK），其餘派工
一個字都不用付。分工判準：rules/ 放**每個 context 都必須知道**的，
agent_doc/ 放**某個角色偶爾需要**的。

| 子層 | 擁有者 | 安裝行為 |
|---|---|---|
| `agent_doc/*.md` | plugin | 每次 install/升級都覆寫 |
| `agent_doc/<語言>/*.md`（如 `zh_tw/`、`en_us/`） | plugin | 剛好一層語言／主題子目錄，通用探測（除 `customize/` 以外任何子目錄都算）；每次 install/升級覆寫，uninstall 時逐檔移除，處理方式與 flat 檔案相同 |
| `agent_doc/customize/` | 使用者 | 只在不存在時複製（需 `--with-optional`），uninstall 後存活；與 base 檔**相同相對路徑**的檔案會**疊加**讀取，衝突處以 customize 為準 |

| 文件 | 讀者 | 觸發條件 |
|---|---|---|
| `codex-cli.md` | 任何要呼叫 Codex CLI 的角色 | 組 codex 呼叫之前 |
| `builder-codex.md` | gondor-builder、dwarf-smith | 機器上有 codex 且派工沒寫 `no-codex` |
| `eagle-codex-prescreen.md` | eagle-sentinel | HIGH-RISK 判定 + 有 codex + 沒寫 `no-codex` |
| `noldor-browser.md` | noldor-loremaster | WebFetch 只拿到 JS 空殼；也收錄 bot-verifier（CAPTCHA）留窗協議 |
| `bilbo-scribe.md` | bilbo-scribe | 每次派工的第一步——routing table ＋共用寫作核心（六步流程、五維度自評、事實保存） |
| `zh_tw/patterns.md`、`zh_tw/style.md`、`zh_tw/localization.md` | bilbo-scribe | 輸出／目標語言為 zh-TW |
| `en_us/patterns.md`、`en_us/style.md` | bilbo-scribe | 輸出／目標語言為英文 |
| `seo-writing.md` | bilbo-scribe | 任務屬 SEO／搜尋導向內容 |
| `tone-development.md` | bilbo-scribe | 任務要求開發或套用特定品牌／作者語氣 |
| `user-guide-ste.md` | bilbo-scribe | 任務屬使用手冊／操作說明／步驟文件 |
| `scene-calibration.md` | bilbo-scribe | 寫全新作品時（一律）；編輯既有文字且指名目標平台／文類時 |

`institution_guard` 對 `~/.claude/agent_doc/` 的保護與 rules/、agents/ 相同：
主 session 直接編輯會被 deny，被派工的 subagent 放行。

## Hooks（選配）

四個 hook **預設皆靜默**——前三個靠環境變數啟用，第四個靠註冊安裝。任何內部
錯誤一律 fail-open（放行，不擋工作）。`install.sh` 會複製 hook 腳本，但不接線
也不啟用（不寫 `hooks.json`、不設環境變數）；要接線請走 plugin 安裝。

| Hook | 事件 | 說明 | env key |
|---|---|---|---|
| `institution_guard` | PreToolUse | 擋主 session 直接 Edit/Write 制度檔（`~/.claude/institution/`、`rules/`、`agents/`，以及任何位置的 `CLAUDE.md`／`AGENTS.md`）——執行「指揮官不下場」；subagent 的編輯一律放行 | `TLOR_INSTITUTION_GUARD=1` |
| `dispatch_guard` | PreToolUse | 擋派工到 `general-purpose`／`claude`／`explore`／`plan`；`bombadil-freeagent` 需 prompt 內帶 `no-role-fits` 字樣才放行（model/effort 已在 frontmatter pin 定，per-call `model` 覆寫為選配） | `TLOR_DISPATCH_GUARD=1` |
| `verify_gate` | Stop | 攔「沒有證據的完成宣稱」：本輪改了程式碼卻沒跑測試指令，擋回一次要求補 fail-then-pass 證據 | `TLOR_VERIFY_GATE=1` |
| `stdd_test_guard` | PreToolUse | STDD 執行期保護：`tasks.md` 中 `[wip]` 任務所引用的測試檔，在該任務標成 `[x]` 前不得再被 Edit/Write | 無啟用 env；由 `install.sh --install-hook` 註冊進 `settings.json` |

三則補充：

- **PreToolUse 三者是串接的**：`hooks.json` 只掛 `pre_tool_use.sh` 一支，它先跑
  `institution_guard.py`，**有輸出就短路**，沒有才輪到 `dispatch_guard.py`。
- **bash fallback 需要 jq**：偵測不到 `python3` 時退回 `institution_guard.sh`，
  它依賴 `jq`；缺 `jq` 會靜默放行（不報錯、不擋）。
- **`TLOR_STDD_ALLOW_TEST_REWRITE=1` 是繞過，不是開關**：它單次解除
  `stdd_test_guard` 的封鎖（plan-drift 復原用），不會啟用任何 hook。

### Session-snapshot 誠實提醒

Claude Code 只在 session 啟動時讀取一次 `settings.json` 裡的 PreToolUse
hook——在既有或 `--continue`/`--resume` 的 session 中新註冊 hook 不會讓它
在那個 session 生效。任何新註冊的 hook 都請只在全新 session 中驗證。
