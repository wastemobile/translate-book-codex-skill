# 代碼審查與改進說明

本文件記錄 2026-04-09 對 `translate-book-codex-skill` 專案進行的完整代碼審查結果，
包括發現的 bug、修復方式、功能改進建議，以及除錯時的注意事項。

---

## 一、發現的 Bug 與修復

### Bug #1｜模型名稱常數不一致（高影響）

**檔案：** `scripts/ollama_stage_translate.py`、`scripts/ollama_stage_refine.py`

**問題：**

Stage 2/3 腳本的預設模型 ID 使用 `mxfp8`/`mxfp4` 後綴，
但本地 MLX 伺服器實際提供的模型 ID 是 `8bit`/`4bit` 後綴。

```python
# ollama_stage_translate.py（修復前）
DEFAULT_MODEL = "gemma-4-e4b-it-mxfp8"    # ← 錯誤

# ollama_stage_refine.py（修復前）
DEFAULT_MODEL = "gemma-4-26b-a4b-it-mxfp4" # ← 錯誤

# run_book.py / preflight.py（原本已正確）
DEFAULT_STAGE2_MODEL = "gemma-4-e4b-it-8bit"
DEFAULT_STAGE3_MODEL = "gemma-4-26b-a4b-it-4bit"
```

**後果：** Preflight 以正確的 `8bit`/`4bit` 名稱查詢 API，會通過；但 Stage 2/3
在執行時以 `mxfp8`/`mxfp4` 發出請求，伺服器回傳 404 / model-not-found，
整個翻譯流程在 preflight 通過後才於執行階段失敗，且沒有清楚的錯誤提示。

**修復：** 將 Stage 腳本的 `DEFAULT_MODEL` 統一改為 `8bit`/`4bit`，
與 `run_book.py`、`preflight.py` 及伺服器實際 model ID 對齊。

---

### Bug #2｜pipeline stage 失敗時崩潰而非回傳結構化 JSON（高影響）

**檔案：** `scripts/run_book.py`

**問題：**

```python
# 修復前
def run_step(step_name, command):
    subprocess.run(command, check=True)  # check=True 在失敗時丟出例外
    return {"name": step_name, "command": command}
```

`subprocess.CalledProcessError` 會沿著呼叫堆疊向上傳播，導致整個 Python 行程以 traceback
結束，而非回傳預期的 JSON report。

**修復：**

```python
def run_step(step_name, command):
    try:
        subprocess.run(command, check=True)
        return {"name": step_name, "status": "ok", "command": command}
    except subprocess.CalledProcessError as exc:
        return {"name": step_name, "status": "fail", "error": str(exc), "command": command}
```

同時，`run_pipeline()` 在每個 step 後檢查 `status`，一旦失敗就提前返回，
避免後續 stage 在損壞的中間狀態上繼續執行。

---

### Bug #3｜chunk_audit missing_source issue schema 不完整（中影響）

**檔案：** `scripts/chunk_audit.py`

**問題：** 當 source chunk 檔案不存在時，`audit_temp_dir()` 建立的 issue 物件只有 3 個欄位，
而正常 audit 失敗的 issue 物件有 6 個欄位。任何統一遍歷 `report["issues"]` 的程式碼都可能
因此遇到 `KeyError`。

```python
# 修復前（缺少 normalized_text、regional_auto_fixes、regional_flagged_variants）
issue = {
    "source": source,
    "reasons": ["missing_source"],
    "regional_opencc_available": ...,
}

# 修復後（與其他 issues 結構一致）
issue = {
    "source": source,
    "reasons": ["missing_source"],
    "normalized_text": "",
    "regional_opencc_available": ...,
    "regional_auto_fixes": [],
    "regional_flagged_variants": [],
}
```

---

### Bug #4｜promote 時多餘的 shutil.copyfile 立刻被覆寫（低影響，但有時序風險）

**檔案：** `scripts/chunk_audit.py`

**問題：**

```python
# 修復前
if promote:
    shutil.copyfile(refined, output)          # (1) 複製原始 refined
    if regional_lexicon_auto_fix:
        with open(output, "w", ...) as handle:
            handle.write(result["normalized_text"])  # (2) 立刻用正規化內容覆寫
```

第一步的 `copyfile` 是多餘的 I/O，而且在兩個操作之間如果行程被中斷，
`output` 會是一個未正規化的中間狀態，與最終應有的內容不同。

**修復：** 合為一次寫入。`result["normalized_text"]` 在 `regional_lexicon_auto_fix=False`
時已等於原始翻譯文字（由 `audit_chunk()` 保證），因此可以無條件使用。

---

### Bug #5｜naer_terms ODS padding row 可能造成 OOM（中影響）

**檔案：** `scripts/naer_terms.py`

**問題：** ODS 試算表的空白尾端欄位通常以 `number-columns-repeated="1024"` 標記。
`_expand_row_cells()` 無限制地將其展開為 Python list，對有許多資料列的詞彙表可能造成
數百萬個空字串物件被配置在記憶體中。

```python
# 修復前
cells.extend([text] * repeat)  # repeat 可能是 1024+

# 修復後
repeat = raw_repeat if text else min(raw_repeat, 16)
cells.extend([text] * repeat)
```

只對空白字元內容（即 padding cell）進行上限限制；有實際文字的 cell 不受影響。

---

### Bug #6｜zh_variant_lexicon.py 集合中有重複條目（輕微）

**檔案：** `scripts/zh_variant_lexicon.py`

**問題：** `LOW_CONFIDENCE_MULTI_TOKEN_PREFIXES` 集合中，`"关于"` 出現兩次：

```python
LOW_CONFIDENCE_MULTI_TOKEN_PREFIXES = {
    "关于",  # ← 第一次
    "对于",
    "对於",
    "關於",
    "关于",  # ← 重複
    ...
}
```

Python set 會靜默去重，所以執行時沒有影響，但這是 copy-paste 錯誤的跡象，
並且讓集合的審查更困難。**修復：** 移除其中一個。

---

### Bug #7｜repair_terminology_mismatches 遍歷過時的 issues 列表（中影響）

**檔案：** `scripts/ollama_stage_refine.py`

**問題：** 術語修復迴圈遍歷最初的 `mismatch_report["issues"]`，
即使在成功修復一個問題後 `repaired` 和 `current_report` 都已更新，
後續迭代仍使用舊的問題列表：

```python
# 修復前
for issue in mismatch_report["issues"]:  # ← 整個迴圈都用最初的列表
    ...
    if candidate_report["mismatches"] < current_report["mismatches"]:
        repaired = candidate
        current_report = candidate_report  # 更新了，但 for 迴圈的來源沒變
```

後果：
1. 已被前一次修復解決的問題，仍會產生多餘的 prompt 呼叫（浪費 LLM 次數）
2. 前一次修復引入的新問題，永遠不會被嘗試修復

**修復：** 改為每次從 `current_report["issues"][0]` 取出目前最迫切的問題：

```python
max_passes = len(mismatch_report["issues"])
for _ in range(max_passes):
    if not current_report["issues"]:
        break
    issue = current_report["issues"][0]   # ← 永遠處理目前狀態中的第一個問題
    ...
```

---

### Bug #8｜naer_terms row_hash 使用 pipe 分隔符，有碰撞風險（低影響，但正確性問題）

**檔案：** `scripts/naer_terms.py`

**問題：**

```python
# 修復前
row_hash = "|".join([dataset, domain, row["sheet_name"], normalized_source, target_term])
```

如果任何欄位本身包含 `|`，不同的資料組合可能產生相同的 hash，
導致 `INSERT OR IGNORE` 靜默丟棄其中一筆。

**修復：**

```python
row_hash = hashlib.sha256(
    json.dumps([dataset, domain, row["sheet_name"], normalized_source, target_term],
               ensure_ascii=False).encode()
).hexdigest()
```

⚠️ **遷移注意事項：** 此修復會改變現有資料庫中已存在資料列的 hash 格式。
若你的 `.sqlite3` 詞彙表是用修復前的版本匯入的，下次執行 `naer_terms.py import`
時，相同的資料列會以新 hash 重新插入（`INSERT OR IGNORE` 不再去重），
導致資料重複。建議在升級後刪除既有 `.sqlite3` 並重新匯入。

---

## 二、功能改進建議（待後續 PR）

### 建議 A｜建立 constants.py 集中管理模型預設值

目前 `run_book.py`、`preflight.py`、`ollama_stage_translate.py`、`ollama_stage_refine.py`
各自定義模型預設值，且彼此不一致（如本次 Bug #1 所示）。
建議建立 `scripts/constants.py`：

```python
# scripts/constants.py
DEFAULT_STAGE2_MODEL = "gemma-4-e4b-it-8bit"
DEFAULT_STAGE3_MODEL = "gemma-4-26b-a4b-it-4bit"
DEFAULT_PROVIDER = "omlx"
DEFAULT_API_BASE = "http://127.0.0.1:8000/v1"
```

所有腳本 `from constants import DEFAULT_STAGE2_MODEL` 即可，不再各自定義。

---

### 建議 B｜為 run_book.py 加入 --dry-run 旗標

目前測試 pipeline 設定的唯一方式是真正執行整個流程。
加入 `--dry-run` 可以讓使用者在不執行 LLM 的情況下檢驗命令構成是否正確：

```bash
python3 scripts/run_book.py --input-file ./book.epub --dry-run
# 輸出：每個 stage 將執行的命令，但不實際執行
```

---

### 建議 C｜chunk_audit.py main() 輸出改為 JSON

`chunk_audit.py` 的 `main()` 目前用 `print()` 輸出 Python dict，
格式無法被機器可靠地解析（key 用單引號，bool 是 `True`/`False`）。
應改為 `json.dumps(result, ensure_ascii=False, indent=2)`，
與 `run_book.py` 和 `preflight.py` 保持一致。

---

### 建議 D｜merge_and_build.py 不應直接呼叫 sys.exit()

`load_config()` 和幾個錯誤路徑直接呼叫 `sys.exit(1)` 而非丟出例外，
導致整個模組難以進行單元測試。應改為：

```python
def load_config(temp_dir):
    config_file = os.path.join(temp_dir, 'config.txt')
    if not os.path.exists(config_file):
        raise FileNotFoundError(f"config.txt not found in {temp_dir}")
    ...
```

---

### 建議 E｜naer_terms 詞彙匹配增加大小寫不敏感選項

目前 `_term_matches_source()` 對大寫縮寫（如 `API`、`CPU`）使用嚴格大小寫匹配，
對含大寫的詞語也是如此。但對一般小寫單字詞語，是透過加空格的 normalized text 比對，
這在句首單字或夾在標點之間的詞語可能漏判。建議：

1. 在 normalized text 比對前後，額外用 word-boundary regex 做 fallback
2. 提供 `--glossary-case-sensitive/--no-glossary-case-sensitive` 旗標

---

## 三、除錯備忘

### 常見失敗場景與處理方式

**1. Preflight 回報模型不存在，但 LLM 服務確定有啟動**

```
{"name": "stage2_model", "status": "fail", "detail": "missing model id: gemma-4-e4b-it-8bit"}
```

**原因：** Bug #1（已修復）。Stage 腳本使用 `mxfp8`/`mxfp4` 後綴，但伺服器實際 model ID 是 `8bit`/`4bit` 後綴。

**處理：** 升級到本 PR 後問題消失。臨時繞過方式：

```bash
python3 scripts/run_book.py --input-file ./book.epub \
  --stage2-model gemma-4-e4b-it-8bit \
  --stage3-model gemma-4-26b-a4b-it-4bit
```

---

**2. run_book.py 在某個 stage 後無輸出就退出**

修復前（Bug #2），convert/draft/refine/audit 任何一個腳本以非零 code 退出，
`subprocess.CalledProcessError` 會讓 run_book.py 的 Python 行程直接崩潰，
stdout 沒有任何 JSON。修復後，失敗的 step 會被記錄在 report 的 `steps` 陣列中。

除錯方式：

```bash
# 直接執行該 stage 腳本，看詳細錯誤
python3 scripts/ollama_stage_translate.py \
  --temp-dir ./book_temp \
  --target-lang "Traditional Chinese"
```

---

**3. 詞彙庫匯入後查詢沒有命中**

可能原因：
- 使用了修復前的版本，row_hash 格式已不同（若升級後重新匯入可解決）
- `normalize_term()` 對來源詞語的處理方式與搜尋時不同步（例如包含 `/` 的術語）
- 該術語被 `GENERIC_SINGLE_WORD_TERMS` 或 `LOWERCASE_STOPWORD_TERMS` 過濾

除錯指令：

```bash
python3 scripts/naer_terms.py query \
  --db ./terms.sqlite3 \
  --chunk ./chunk0001.md \
  --format json | python3 -m json.tool
```

---

**4. 區域詞彙（OpenCC）審查結果異常**

若 `audit` 報告中 `regional_opencc_available` 為 `false`，但系統確定安裝了 OpenCC：

```bash
python3 -c "import opencc; print(opencc.__version__)"
```

`zh_variant_lexicon.py` 透過 `try: import opencc` 處理，若 import 名稱與已安裝套件不符
（例如套件是 `opencc-python-reimplemented` 但 import 名稱是 `opencc`），需確認對應關係。

---

## 四、測試執行方式

```bash
# 安裝測試依賴
pip install -r requirements-dev.txt

# 執行完整測試套件（從 repo root）
python -m pytest tests/ -v

# 執行單一測試檔
python -m pytest tests/test_chunk_audit.py -v

# 只跑與本次修復相關的測試
python -m pytest tests/test_run_book.py tests/test_chunk_audit.py tests/test_naer_terms.py -v
```

所有測試皆在 `tests/` 目錄中，透過 `sys.path.insert` 手動加入 `scripts/`，
因此必須從 repo root 執行（不需 `cd scripts`）。
