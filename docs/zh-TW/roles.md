# 角色與派工

[← 回 README](../../README.zh-TW.md)

## 世界觀

- **你（工程師）是伊露維塔（Ilúvatar）**——意志的源頭。
- **主 Claude session 是邁雅（Maia）**——解讀你的意志、召集遠征隊、
  派遣諸族；自己不下場跑腿。
- **Subagents 是中土諸族**——各自生而註定（frontmatter）：跑什麼模型、
  想多深、能碰哪些工具。

## 遠征隊名冊

| 角色 | 種族與職位 | Model / effort | 職責 |
|---|---|---|---|
| `rohirrim-outrider` | 洛汗外圍騎哨 | haiku / low | 快速定點查找：「X 在哪／Y 怎麼運作」 |
| `ranger-pathfinder` | 北方遊俠 | sonnet / low | 漏掉代價高時的廣域唯讀掃查 |
| `noldor-loremaster` | 諾多精靈博學者 | sonnet / medium | web/文件研究：附來源與版本、事實與推論分明 |
| `dwarf-smith` | 矮人鍛造師 | sonnet / low | 規格完全明確的機械工作；絕不即興 |
| `gondor-builder` | 剛鐸石匠 | sonnet / medium | 照明確 spec 實作、容許區域性小判斷；設計歧義留給 Maia |
| `eagle-sentinel` | 巨鷹哨兵 | opus / medium | Fresh-context 對抗式驗證；CONFIRMED/REFUTED |
| `mirror-of-galadriel` | 凱蘭崔爾之鏡 | haiku / low | 唯讀查詢外部系統（任務追蹤、文件庫），透過 session 的 MCP 工具——只看，不動手 |
| `palantir-stone` | 真知晶石 | sonnet / medium | 唯一能透過 session MCP 工具**寫入**外部系統的角色；照派工列舉的內容逐字執行，自己不判斷寫什麼 |
| `cirdan-shipwright` | 造船者刻爾丹 | opus / medium | 開放式的 diff 設計／production-readiness 審查——沒有準則清單、沒有結論可攻；有準則的活留給 `eagle-sentinel`，攻結論的活交給下方的抗辯審查小組 |
| `bilbo-scribe` | 紅皮書作者比爾博 | opus / medium | 照 spec/outline 寫專業文章，或把既有文字去 AI 味、改到像人寫的——寫作與編輯共用同一套 pattern catalog；絕不自證完稿（那是 `eagle-sentinel` 的活） |
| `bombadil-freeagent` | 湯姆·龐巴迪 | sonnet / medium | 名冊之外的自由角色，用於現有角色都不合的任務形狀。預設 pin sonnet/medium——可用 per-call `model` 升降級（effort 沒有 per-call 機制）；每次派工必須在 prompt 寫 `no-role-fits reason:`——由 `hooks/dispatch_guard.py` 強制。同一種不合形狀出現第二次，就該鑄造新角色而不是再用它 |

### 抗辯審查小組（rivendell-council 鏡頭）

這三個鏡頭平時不接一般派工——高風險判定時由 `eagle-sentinel` 建議、**Maia 召集**（≥3 個獨立鏡頭＋一位裁判，流程見 `rivendell-council` skill）。例行或邊界案的召集，派遣鏡頭時可明示 `model: sonnet` 降級——派遣時的覆寫優先於角色的 frontmatter pin。

| 角色 | 種族與職位 | Model / effort | 職責 |
|---|---|---|---|
| `elf-archer` | 精靈神射手 | opus / medium | 正確性鏡頭：每一箭命中一個邏輯漏洞 |
| `orc-saboteur` | 半獸人破壞者 | opus / medium | 安全與失效鏡頭：輸入驗證、競態、部分失敗 |
| `hobbit-gardener` | 哈比人園丁 | opus / medium | 簡潔性鏡頭：修剪過度工程 |

## 外部系統讀寫配對

`mirror-of-galadriel`（讀）與 `palantir-stone`（寫）是名冊中唯二會透過
session MCP 工具碰觸 repo/session 之外系統的角色。所有讀取派給鏡子；所有
寫入派給真知晶石，且僅能以列舉清單方式派工（目標 gid＋標題、變更前預期值、
逐字新值）——每次派工上限 10 筆，且依 risk-tiers T1，Maia 必須在派工前
取得使用者對這份確切列舉內容的明確確認。兩個角色的 agent 檔案
（`agents/mirror-of-galadriel.md`、`agents/palantir-stone.md`）才是完整
規則（範圍界定、驗證、冪等性等）的權威來源——本節只講派工路由，不重述細節。

若某個 session 的 MCP server 曝露的工具名稱與 `tools:` frontmatter 不同、
或釘住的 server 根本沒連上：工具**全部**解析失敗（零個可用工具）時，角色
會無法啟動並回報缺哪些工具；工具**部分**解析失敗時，未解析到的工具會被
靜默忽略、角色仍會啟動（已驗證的 harness 行為，v2.1.208+）——這時要連上
對應的 MCP server，或把 `tools:` 清單改成你 session 實際曝露的工具名稱。

## Subagent 派工（輕量版 CLAUDE.md snippet）

**輕量使用者**（只裝 plugin、不跑 `/tlor-init`）：在你專案的 CLAUDE.md
加這段，不必完整安裝 rules 也能有派工紀律：

```markdown
## Subagent dispatch (tlor-orchestration)

Prefer the pinned tlor-orchestration roles over generic subagents:
- Targeted code/config lookup ("where is X") → rohirrim-outrider
- Broad/ambiguous search where a miss is costly → ranger-pathfinder
- Web/docs research, version checks → noldor-loremaster
- Mechanical batch edits with an exact recipe → dwarf-smith
- Implement against a written spec → gondor-builder
- Verify finished work (fresh context; never self-certify) → eagle-sentinel
- Adversarial review of major conclusions → elf-archer + orc-saboteur + hobbit-gardener in parallel
- Read an external system via session MCP tools → mirror-of-galadriel
- Write to an external system via session MCP tools (enumerated mutations only) → palantir-stone
- Open-ended design/production-readiness review of a bare diff (no criteria, no conclusion to attack) → cirdan-shipwright
- Write a professional article, or de-AI existing prose → bilbo-scribe
- No pinned role fits the task's shape (verify the whole table first — a naming slip is not a missing role) → bombadil-freeagent

Delegate any read of >3 files or repo-wide scan; keep only conclusions + file:line in the main thread.
```
