# 歷史

[← 回 README](../../README.zh-TW.md)

## 更名：tlor-agents → tlor-orchestration（2.x → 3.0）

本 repo 已從 `tlor-agents` 更名為 `tlor-orchestration`；GitHub 會自動轉址舊網址，但 plugin 安裝認的是 repo 名稱，所以要手動走一次：

```
/plugin uninstall tlor-agents@tlor        # 移除舊安裝
/plugin marketplace add twjohnwu/tlor-orchestration
/plugin install tlor@tlor   # 以新名稱重新加入
```

若你是用 `install.sh`（直接複製）安裝的，重新跑新版 `install.sh` 即可
升級時實際變動請見 [installation.md](installation.md) 的所有權模型。

**v3.0.0 同時改變了安裝／所有權模型**（見 [installation.md](installation.md)）：
base rule 檔案現在由 plugin 擁有，每次安裝都無條件覆蓋；想跨版本保留的內容一律放進 `rules/customize/`，installer 永遠不會動它。若你在 2.x 曾就地手改過 base rule 檔案，升級前把修改搬進 `rules/customize/`，否則下次安裝就會被官方版本蓋掉。

## 版本重置（3.0.0 → 0.0.1）

本專案走過三個架構階段：
(1) agents role base（1.x——九個固定角色定義）
(2) rule-assigned agents（2.x–3.0——角色與制度派工規則接線）
(3) orchestration（0.x——完整的編排框架；STDD 等流程管線將被整合進來）。這次定位重整讓版本號重新從 0.0.1 開始。

已安裝 2.x/3.x 的機器**不會**透過 `/plugin marketplace update` 收到較低的版本號（依 Claude Code 的 plugin 版本解析規則，版本降級會被忽略）。要遷移：先解除安裝 plugin、移除 marketplace、重新加入 marketplace，再重新安裝。

完整的逐版本紀錄（含這次定位重整前後的所有版本）請見 [release_log.md](../release_log.md)。
