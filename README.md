# mosAIc

第一版正式網頁前端：Next.js App Router＋React＋TypeScript，依 Figma 畫面與 [MOSAIC 前端對接](https://claude.ai/artifact/VKcqRCFHdSMFTxTCfqf7wA) 實作。FastAPI 負責所有 API 與生成流程。

## 專案位置

- `apps/web`：網頁、元件、上傳與結果頁。
- `apps/backend`：原有 Python / FastAPI 後端；邏輯、資料與測試保留。
- `apps/mobile`：原 mobile 預留目錄，尚未建立 Expo app。
- `packages/api`、`types`、`core`、`design`：共用 API client、資料型別、上傳驗證、設計變數。
- `docs/architecture/api-contract.md`：API 對接規則。
- `content/recipes`：未來編輯內容的預留位置；後端資料仍在 `apps/backend/data/recipes.json`。

原 `frontend/website` → `apps/web`；`frontend/mobile` → `apps/mobile`；`backend` → `apps/backend`；`frontend/shared/types` → `packages/types`。原本網頁目錄只有佔位檔案，因此這次一併完成搬移。

## 本機啟動

需要 Node.js 24 以上、pnpm 11.19.0、Python 3.10 以上。以下命令都從 repo 根目錄執行。

```sh
pnpm install
python -m venv apps/backend/.venv
```

Windows：

```powershell
apps/backend/.venv/Scripts/python.exe -m pip install -r apps/backend/requirements.txt
apps/backend/.venv/Scripts/python.exe -m uvicorn app.main:app --app-dir apps/backend --port 8000
```

macOS / Linux：

```sh
apps/backend/.venv/bin/python -m pip install -r apps/backend/requirements.txt
apps/backend/.venv/bin/python -m uvicorn app.main:app --app-dir apps/backend --port 8000
```

另外開一個終端機執行 `pnpm dev`，瀏覽 `http://localhost:3000`。完成安裝後，macOS / Linux 也可以使用 `bash scripts/dev.sh` 同時啟動前後端。

後端如使用其他位址，在 `apps/web/.env.local` 設定 `BACKEND_URL=http://127.0.0.1:8010`，再啟動前端。範本見 `apps/web/.env.example`。Backend 的環境變數請參考 `apps/backend/.env.example`；金鑰只放後端。

## 檢查與正式部署

```sh
pnpm typecheck
pnpm test
pnpm build
pnpm start
```

後端測試：啟用後端 virtualenv 後，執行 `cd apps/backend`、`python -m unittest discover -s tests -v`。

正式部署需要 Next.js server 與 FastAPI server。`/api/*`、`/static/*` 由 Next.js 代理至 `BACKEND_URL`；75 秒代理與生成等待時間支援後端同步生成。設定正式後端位址後再建置，確保部署平台也允許至少 75 秒請求。這份 app 不使用靜態匯出。

## 第一版功能與目前狀態

真實 recipe 列表與詳細頁、裝置內收藏、JPEG / PNG / WebP 上傳預覽（最大 8MB）、同步生成、持久化結果連結、live / cached / mock 來源揭露、原始貼文連結與七種 API 錯誤均已對接。所有模式原樣顯示後端 `sourceNote`；prompt 不會打包到前端。

目前三份 seed 的 `tryReady` 都是 `false`，AI provider 尚未實作。前端會停用試用與上傳，直到後端完成核實與 provider。Terms / Privacy 尚無正式文件，因此未提供假連結。收藏只儲存在目前瀏覽器，尚無帳號同步。

先前的靜態 Sites 預覽是歷史原型；本 repo 是正式前端原始碼，不含假生成流程。詳細範圍與下一步見 `PROJECT.md`、`ROADMAP.md`。
