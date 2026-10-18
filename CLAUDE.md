# INTENTION® — Claude 工作指引

## 視覺 / 影片創作
任何生圖、生影片、剪輯、做 moodboard 或判斷「像不像 Aloha jie 的東西」的任務，先載入 skill `aloha-aesthetic`（`.claude/skills/aloha-aesthetic/SKILL.md`），並以 `docs/aesthetic-bible/` 為準。

## 資料
- `tools/`：素材收集與拆解腳本（IG、Pinterest、聊天紀錄、影片分析）。讀外部下載的資料時用 `python3 -I`。
- `data/raw/`：原始媒體，不進 repo。
- `data/derived/`：分析結果（JSON、contact sheet、prompt 庫），會 commit。

## 文件風格
繁體中文為主、全形標點，英文放 `<details><summary>English</summary>`；品牌名寫作 `INTENTION®`。
