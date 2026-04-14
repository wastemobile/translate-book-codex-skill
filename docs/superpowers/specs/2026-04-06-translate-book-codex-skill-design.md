# Translate-Book Codex Skill Design

## Goal

將 `deusyu/translate-book` 的 Claude Code Skill 改寫為可重複使用的 Codex Skill，保留原有前後處理與電子書打包流程，並將中段翻譯流程改為四階段混合式編排：

1. 內建大模型先翻少量 chunks 作為基準樣本
2. 本機 `gemma-4-e4b-it-8bit` 進行快速初譯
3. 本機 `gemma-4-26b-a4b-it-8bit` 進行逐 chunk 細修
4. 內建大模型對高風險 chunks 做最後檢查與潤飾

並行策略以品質與穩定性為優先，預設單線，通常不超過 2 個並行任務，只有品質穩定時才允許升到 3。

## Existing Workflow To Preserve

原始專案的核心管線應完整保留：

- `scripts/convert.py`
  - 使用 Calibre `ebook-convert` 將 PDF/DOCX/EPUB 轉成 HTMLZ
  - 解出 HTML 與圖片
  - 使用 Pandoc（透過 `pypandoc`）將 HTML 轉成 Markdown
  - 拆成 `chunk*.md`
  - 產生 `manifest.json` 與 `config.txt`
- `scripts/manifest.py`
  - 追蹤 source chunk hash
  - 合併前驗證 source/output 對應完整性
- `scripts/merge_and_build.py`
  - 驗證 chunk 完整性
  - 合併譯文
  - 使用 Pandoc 轉成 HTML
  - 使用 Calibre 輸出 `docx`、`epub`、`pdf`
- HTML 模板
  - `template.html`
  - `template_ebook.html`

因此 Codex 版不重新發明轉檔與打包工具鏈，只替換翻譯 orchestration。

## Target Skill Structure

正式 skill 安裝於：

`~/.codex/skills/translate-book/`

建議結構：

```text
translate-book/
├── SKILL.md
├── agents/
│   └── openai.yaml
└── scripts/
    ├── calibre_html_publish.py
    ├── convert.py
    ├── manifest.py
    ├── merge_and_build.py
    ├── template.html
    ├── template_ebook.html
    ├── ollama_stage_translate.py
    ├── ollama_stage_refine.py
    └── chunk_audit.py
```

## Runtime Model Strategy

### Stage 1: Baseline Sample Translation

由 Codex 內建大模型直接處理少量 chunks，建立風格與術語基準。

- 預設樣本數：3
- 預設選擇：
  - `chunk0001`
  - `chunk0002`
  - 一個正文代表 chunk
- 若書籍前段是目錄或版權頁，可改由 skill 重新選擇樣本

這些樣本同時扮演兩個角色：

- 成為風格參考
- 成為對應 chunk 的最終譯文候選

### Stage 2: Fast Draft Translation

由本機 `gemma-4-e4b-it-8bit` 進行全量初譯。

- 輸入：`chunk*.md`
- 輸出：`draft_chunk*.md`
- 目標：保格式、保段落、保標記、快速完成全量底稿

### Stage 3: Local Refinement

由本機 `gemma-4-26b-a4b-it-8bit` 針對每個 `draft_chunk*.md` 細修。

- 輸入：原文 `chunk*.md` + 初譯 `draft_chunk*.md`
- 輸出：`refined_chunk*.md`
- 目標：修正常見誤譯、統一語氣、改善繁中表達，但不重組內容

### Stage 4: Final Audit And Polish

由 Codex 內建大模型只處理高風險 chunks 的最後檢查與潤飾。

- 輸入：原文 `chunk*.md` + `refined_chunk*.md`
- 輸出：`output_chunk*.md`
- 若某 chunk 未被抽中終審，且 audit 通過，則直接將 `refined_` 複製為 `output_`

## Chunk File Lifecycle

每個 chunk 分階段保存，避免單一輸出被覆蓋後失去可追查性。

- `chunk0001.md`
  - 原文 chunk
- `sample_chunk0001.md`
  - 第 1 階段大模型建立的樣本譯文，只存在於少量樣本
- `draft_chunk0001.md`
  - 第 2 階段 `gemma-4-e4b-it-8bit` 初譯
- `refined_chunk0001.md`
  - 第 3 階段 `gemma-4-26b-a4b-it-8bit` 細修
- `output_chunk0001.md`
  - 最終輸出，唯一參與 merge/build 的譯文

此設計允許：

- 回溯哪一階段引入問題
- 重新跑單一階段而不破壞其他成果
- 比對 `draft`、`refined`、`output` 的差異

## Status Model

每個 chunk 在 pipeline 中可落於以下狀態：

- `sampled`
  - 已建立 `sample_`
- `drafted`
  - 已建立 `draft_`
- `refined`
  - 已建立 `refined_`
- `finalized`
  - 已建立 `output_`
- `failed`
  - 輸出缺失、空白、異常短、Markdown 結構損壞、殘留明顯未譯內容或保留錯誤標記

## Parallelism Rules

Codex 版 skill 不採原專案預設 `8` 工並行。

並行規則：

- 預設 `1`
- 建議上限 `2`
- 僅在品質穩定且本機模型狀況良好時允許 `3`
- Stage 1 與 Stage 4 一律單線
- Stage 2 與 Stage 3 才允許有限並行

原因：

- 降低本機模型崩潰與風格漂移風險
- 降低 API/模型資源耗盡
- 便於檢查壞稿與重試

## Audit Rules

需新增 `chunk_audit.py`，用於合併前與 Stage 4 前的風險篩選。

高風險條件包括：

- 譯文為空
- 譯文過短，和原文長度比例顯著異常
- 殘留大段英文
- Markdown 標題、連結、圖片、註腳結構明顯不匹配
- 出現保留錯誤標記或 placeholder
- 可疑摘要化、條列化、重組式輸出

`chunk_audit.py` 應輸出：

- 可直接接受的 chunk
- 需重跑 Stage 2 的 chunk
- 需重跑 Stage 3 的 chunk
- 需進 Stage 4 大模型終審的 chunk

## Retry Rules

Stage 2 與 Stage 3 皆採保守重試：

- 每個 chunk 最多 2 次
- 若 Stage 2 失敗：
  - 重跑一次 `gemma-4-e4b-it-8bit`
  - 再失敗則交由 audit 標記
- 若 Stage 3 失敗：
  - 保留 `draft_`
  - 不覆蓋成更差的 `refined_`
  - 再重跑一次 `gemma-4-26b-a4b-it-8bit`
- 若 Stage 4 判定 `refined_` 已可用：
  - 直接原樣寫成 `output_`
  - 不必潤句重寫

## Prompting Requirements

四階段都要遵守同一批翻譯約束：

- 保留 Markdown 結構
- 保留圖片引用、連結、註腳與書內標記
- 不輸出解釋、前言、註解或對話
- 不省略段落
- 不改寫為摘要
- 以自然、穩定的繁體中文表達

Stage 2 prompt 要明確要求參考 `sample_` 的語氣與術語。
Stage 3 prompt 要明確限制為「忠實細修，不得重組」。
Stage 4 prompt 要限制為「只修錯與不自然表達，必要時才改寫」。

## Build And Packaging

最終打包仍採原流程：

1. 驗證 `output_chunk*.md`
2. `merge_and_build.py` 合併為 `output.md`
3. 轉成 `book.html`
4. 產出 `book.docx`
5. 產出 `book.epub`
6. 產出 `book.pdf`

依賴必須明確寫入 skill：

- `python3`
- `pandoc`
- `ebook-convert`
- Python 套件：
  - `pypandoc`
  - `beautifulsoup4`（建議）
  - `markdown`（建議）

## User-Facing Skill Behavior

使用者對 Codex 說明要翻譯某本書時，skill 預期：

1. 收集參數
   - `file_path`
   - `target_lang`
   - `sample_count`
   - `parallelism`
   - 額外翻譯指示
2. 執行 `convert.py`
3. 建立樣本 chunk 基準
4. 跑 Stage 2 初譯
5. 跑 Stage 3 細修
6. 執行 audit
7. 對高風險 chunk 做 Stage 4 最終終審
8. 執行 `merge_and_build.py`
9. 回報產物與失敗項

## Testing Strategy

實作後至少應驗證：

- 既有 `convert.py` / `manifest.py` / `merge_and_build.py` 在 skill 內仍可運作
- 新增 `chunk_audit.py` 可正確標出異常短稿與缺檔
- `ollama_stage_translate.py` 能正確為 `draft_` 命名並跳過已完成檔
- `ollama_stage_refine.py` 能以原文 + draft 生成 `refined_`
- `refined_` 無需終審時可正確提升為 `output_`
- 整體流程可在單一 `*_temp/` 目錄完成從 chunk 到 ebook 的重建

## Non-Goals

此版本不處理以下項目：

- 將 Stage 1 與 Stage 4 完全腳本化為可離線自動執行
- 建立通用雲端 API 供應商抽象層
- 追求高並行吞吐量
- 自動做術語表或人名表管理系統

這些可在後續版本再擴充。
