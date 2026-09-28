# mosAIc

AI Creative Playground — 整理創作者公開分享的圖片生成 prompt，讓人看得到原作者、
也能直接用自己的照片試一次。

```
backend/            FastAPI。recipe 查詢、prompt lookup、生成、fallback、result storage
  app/              main.py（HTTP）· generation.py（pipeline）· recipes.py（查詢與 public projection）
  data/             recipes.json —— recipe 的唯一真實來源
  scripts/          pregen.py —— Build Day 前產生 fallback 素材
  storage/          seed（已核實素材）· fallback（預備結果）· results（執行產出，gitignored）
  tests/            test_generation.py（36 項）· test_api.sh（17 項 HTTP contract）

frontend/
  website/          Next.js —— 尚未 scaffold
  mobile/           Expo —— 尚未 scaffold
  shared/           跨端共用：types 已就緒，api client 與 config 待建

docs/
  build-day/        產品範圍、資料定義、Build Day 執行計畫
  backend-architecture.html    後端架構（唯一文件）
  frontend-integration.html    前端對接說明

scripts/dev.sh      同時起 backend 與 website
```

## 跑起來

```bash
python3 -m venv backend/.venv
backend/.venv/bin/pip install -r backend/requirements.txt
./scripts/dev.sh          # 若 :8000 被佔用：PORT=8010 ./scripts/dev.sh
```

## 測試

```bash
cd backend && ./.venv/bin/python -m unittest   # pipeline
./backend/tests/test_api.sh                    # HTTP contract
```

## 現在的狀態

- `_call_provider()` 尚未實作（provider 未選定）→ 所有結果都是 `mock`
- 三份 seed 都是 `tryReady: false` → `POST /api/generate` 一律回 `403 recipe_not_ready`

兩者都是刻意的誠實預設，不是 bug。細節見 `docs/backend-architecture.html`。
