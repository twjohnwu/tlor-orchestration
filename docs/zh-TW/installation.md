# 安裝與所有權

[← 回 README](../../README.zh-TW.md)

## 兩種使用方式

- **輕量**——只裝 plugin。安裝後，任何一個新開的 session 都能使用十三個角色
  （若是在已開啟的 session 中安裝，須先執行 `/reload-plugins`）。請直接
  以名稱明確呼叫角色，或加上 [roles.md](roles.md) 的 CLAUDE.md snippet
  以取得穩定的派工——我們的 headless 測試顯示，僅靠 description 並不能
  穩定觸發自動派工，因此 snippet 是建議的輕量做法。
- **完整**——再加跑 `/tlor-init`。這會落地 rules 檔案、`~/.claude/institution/`
  layout（見下）、以及 CLAUDE.md/AGENTS.md 路由。Rules 檔案本身一旦存在就會
  自行載入——`.claude/rules/` 是原生 auto-load 位置，不需要路由；路由提供
  的是最先讀到的派工紀律提醒、給不讀 `.claude/rules/` 的工具用的 AGENTS.md
  介面，以及宣告本框架的角色是你的主要派工對象。

## 所有權模型

- **Base rules 由 plugin 擁有。** 每次安裝／升級都無條件覆蓋必裝 rule
  檔案，並蓋上 plugin 的 `version`（唯一真相來源——不是寫死在檔案裡的值）。
  別手改這些檔案，下次安裝就會被蓋掉。
- **Agent role 檔案採「先備份再覆蓋」，絕不靜默覆蓋。** Agent
  frontmatter 沒有 import 機制，所以本地編輯（例如替某角色的 `tools:`
  這行加一個 MCP server）只能活在已安裝的檔案裡。`/tlor-init` 與
  `install.sh` 對每個檔案套用同一條規則：檔案不存在 → 直接安裝；與
  bundled 副本逐位元相同（`cmp -s`）→ 不動；有差異（不論是手動客製化
  或只是舊版本）→ 先備份到旁邊的 `<file>.bak-YYYYMMDD-HHMMSS`，再用 bundled
  版本覆蓋。時間戳（不只日期）確保同一天重跑安裝兩次也不會蓋掉前一份備份。
  沒有原廠合併 base、也沒有互動式 Overwrite/Keep/Merge 選單——
  `.bak-YYYYMMDD-HHMMSS` 檔案就是使用者事後手動重新套用客製化內容的來源。
- **`rules/customize/` 是你的。** installer 會建立這個目錄，首次安裝可能
  幫你種入選配的起始檔案，之後**永遠不覆蓋**裡面已存在的任何東西——這是
  唯一該放持久本地客製化內容的地方。
- **Base 檔案沒有任何使用者可寫區塊。** 所有使用者自行新增的內容——
  lessons、skill namespace 優先序表、本地慣例——一律放在 `rules/customize/`，
  絕不放進 base rule 檔案，因為那裡任何追加內容都會在下次無條件覆蓋時被清空。
- **`~/.claude/institution/` layout。** 使用者層級安裝時，
  `~/.claude/{agents,rules,hooks}` 會變成指向 `~/.claude/institution/<name>/`
  的 symlink。這是冪等的：已經是 symlink → 不動；已有真實目錄 → 搬到
  `institution/` 底下再建 symlink（不遺失任何東西）；不存在 → 直接新建。
  這層間接讓 plugin 對 base rules/hooks 的覆蓋式安裝，永遠不會跟你手動
  搬過的目錄打架。

## Session 啟動成本

裝好之後，rules corpus 不是靠 routing 控制載不載入——大部分內容會在**每個
session 開始時整包載入**。`~/.claude/rules/`（連同它的 `customize/` 子目錄）
是 Claude Code 原生的 auto-load 位置：底下每個沒有 `paths:` frontmatter 的
`.md` 檔都會在啟動時遞迴載入進 context，不需要 `@import`。若某個 rule
檔案帶有 `paths:` frontmatter，就是官方支援的延後載入方式——它不在啟動時
載入，只在 Claude 讀到符合該 pattern 的檔案時才觸發載入。

用 `wc -l -c` 對這個 repo 實測（自我量測指令見下方——請自行重跑，這只是
某一次的快照，不是保證值）：

```
$ wc -l -c rules/*.md
     795   44155 total
$ wc -l -c rules/customize/*.md
     350   15795 total
$ cat rules/*.md rules/customize/*.md | wc -l -c
    1145   59950
```

也就是說：六個 base rule 檔案共 **795 行／約 44.2 KB**，種入的
`rules/customize/` 起始檔案共 **350 行／約 15.8 KB**，兩者合計的每 session
下限是 **1,145 行／約 60.0 KB**——這還不含你之後自己加的任何一條 lesson。
這是每個 session 都要付的固定稅，不管那個 session 有沒有派出任何 subagent。
base 數字適用於每一種安裝方式；合計數字則只在你同時裝了選配的
`rules/customize/` 種子檔（`install.sh --with-optional`）時才成立——只裝
base 的安裝只需付 base 那個數字。

這個機制有兩個誠實提醒。**版本下限**：`.claude/rules/` 的 auto-load 需要
Claude Code 2.0.64 以上——舊版根本不讀這個目錄，所以「不需要路由」在舊版上
會變成一條 rule 都沒載入，而不是你以為的輕量 fallback。**它是可以被關掉
的**：任何 settings 層的 `claudeMdExcludes` 都能抑制載入；另外——僅限
project 層 rules——當 `--setting-sources` 排除了 project settings 時，
project 層的 rules 也會被跳過，這一半不適用於使用者層安裝。別假設這包
corpus 是無條件生效的。

這個成本對 context window 較小的模型影響會成比例地更大——而這正是這個
framework 的目標讀者（派工這整套機制的前提就是把 field work 從有限 context
卸載出去）。如果你在意每個 session 的 budget，把這一點跟上面輕量的
plugin-only 路徑放在一起權衡。

## 安裝

### 方式 A——plugin（推薦）

```
/plugin marketplace add twjohnwu/tlor-orchestration
/plugin install tlor@tlor
```

更新：我們 bump `version` 後，用 `/plugin marketplace update tlor` 取得。

### 更新支援

更新支援僅限 marketplace 安裝路徑（方式 A）：
`/plugin marketplace add twjohnwu/tlor-orchestration` 後
`/plugin install tlor@tlor`。每次發布都會 bump
`.claude-plugin/plugin.json` 的 `version`——依 Claude Code 官方 plugin
文件，光是推送 commit 不會讓更新出現，只有版本號變動才會，之後
`/plugin marketplace update tlor` 才拉得到新版。`install.sh` 直接複製路徑
（方式 B）完全沒有更新提示 UI——重跑 `install.sh` 會再次覆蓋 base rules，
但不會通知你有新版本；請自行查 repo 的 releases 或版本徽章。

### 方式 B——直接複製

```bash
git clone https://github.com/twjohnwu/tlor-orchestration.git
cd tlor-orchestration && ./install.sh          # --dry-run / --force / --uninstall / --with-optional / --stdd-role=ALL / --install-hook / --skills-dest=PATH
```

複製 agents 到 `~/.claude/agents/`、rules 到 `~/.claude/rules/`、hook 腳本到
`~/.claude/hooks/`、skills 到 `~/.claude/skills/`，首次執行時建立
`~/.claude/institution/` symlink layout（見上方所有權模型）。加
`--with-optional` 一併安裝 `rules/customize/` 裡的選裝 rules。寫入 manifest
供 `--uninstall` 精確移除。Hook **啟用**（環境變數、`hooks.json` 接線）
仍需走方式 A——`install.sh` 只負責放檔案。

**`--stdd-role=RD|PM|UIUX|ALL`** — 選配安裝 STDD 工作流程 skills
（`stdd-skills/*`，非自動載入；見 [skills.md](skills.md)）。本輪僅實作
`ALL`；`RD`/`PM`/`UIUX` 只會印出 deferred 訊息、不安裝任何東西。不加此旗標
→ 不裝任何 STDD skill，與這個旗標出現前的行為相同。

**`--install-hook`** — 選配安裝並在 `settings.json` 註冊 STDD test-file
guard（`hooks/stdd_test_guard.py`）。預設不安裝。**誠實提醒**：Claude
Code 只在 session 啟動時讀取一次 `settings.json` 裡的 PreToolUse
hook——在既有或 `--continue`/`--resume` 的 session 中執行
`--install-hook` 不會讓 hook 在那個 session 生效；請只在全新 session 中驗證。

**`--skills-dest=PATH`** — 一次性宣告 skills 安裝目錄。`PATH` 必須是絕對
路徑，且不能是 `$HOME` 或 `/` 本身。宣告會持久化到
`~/.claude/.tlor-install.conf`（一行純文字 `skills_dest=PATH`，用
`grep`/`cut` 讀取，絕不 `source`），所以之後不帶旗標重跑也會裝到同一個
位置。沒有宣告時（沒旗標、conf 也沒有這一行），`~/.claude/skills` 若是
指向 `~/.claude` 之外的 symlink，仍會中止整個安裝——這個安全預設是刻意
且不變的；明確宣告 `--skills-dest` 就是你選擇跳出這個預設、為刻意放在
別處的 skills 目錄開後門的方式。

**輕量使用者**（只裝 plugin、不跑 `/tlor-init`）：見 [roles.md](roles.md)
的 CLAUDE.md snippet，不必完整安裝 rules 也能有派工紀律。

### 方式 C——/tlor-init（plugin 安裝後推薦）

方式 A 安裝後，在 Claude Code 中執行 `/tlor-init` 做引導式設定：選安裝
層級、安裝 rules、產生 CLAUDE.md 路由與 AGENTS.md、選配啟用 hooks。

無論哪種方式，裝完**都要開新 session**——agent 定義在 session 啟動時載入。
