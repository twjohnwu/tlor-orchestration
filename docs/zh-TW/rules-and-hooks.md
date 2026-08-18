# Rules 與 Hooks

[← 回 README](../../README.zh-TW.md)

## Rules

本 plugin 附帶去個人化的編排規則——透過 `/tlor-init` 或 `install.sh` 安裝：

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

你也可以把自己團隊的規則檔（`.md`）直接放進 `rules/customize/`——安裝時
會一併複製，且會原生自動載入（跟這裡其他檔案一樣走 `.claude/rules/`
機制，不需要路由表），installer 永遠不會動它。`/tlor-init` 產生的路由表
只是幫不懂 `.claude/rules/`、只讀 AGENTS.md 的工具記錄這個目錄——不是它讓
檔案載入的。

## Hooks（選配）

四個 hook **預設皆靜默**——前三個靠環境變數啟用，第四個靠註冊安裝。任何內部
錯誤一律 fail-open（放行，不擋工作）。`install.sh` 會複製 hook 腳本，但不接線
也不啟用（不寫 `hooks.json`、不設環境變數）——要接線請走 plugin 安裝。

| Hook | 事件 | 說明 | env key |
|---|---|---|---|
| `institution_guard` | PreToolUse | 擋主 session 直接 Edit/Write 制度檔（`~/.claude/institution/`、`rules/`、`agents/`，以及任何位置的 `CLAUDE.md`／`AGENTS.md`）——執行「指揮官不下場」；subagent 的編輯一律放行 | `TLOR_INSTITUTION_GUARD=1` |
| `dispatch_guard` | PreToolUse | 擋派工到 `general-purpose`／`claude`／`explore`／`plan`；`bombadil-freeagent` 需同時帶明確 `model` 參數與 prompt 內的 `no-role-fits` 字樣才放行 | `TLOR_DISPATCH_GUARD=1` |
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
