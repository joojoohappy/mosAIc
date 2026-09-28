# Build Day｜團隊執行計畫

文件目的：
1. 協調活現場決策、三人分工、整合節點與展示備案。
2. Prototype 目標以 [PROJECT.md](PROJECT.md) 為準：整合創作者分享的 prompt，提供作品預覽、原作者連結與平台內試用。Fable5 示範後，由團隊共同決定實作形式。
3. 記錄前後端目標目錄、跨端 API 契約，以及 Figma 設計稿採用與刪減決策。


## Fable5 示範後：10–15 分鐘決策

每位成員記錄一項值得採用的能力、一項尚待確認的限制，以及一個希望觀眾記住的互動。完成下表後開始開發。

| 決定項目 | 團隊結論 |
|---|---|
| **KEEP**：保留的原型設計 | 待填 |
| **CHANGE**：需調整的流程或畫面 | 待填 |
| **ADD**：新增項目與負責人 | 待填 |
| **CUT**：為新增項目刪減的同等工作量 | 待填 |
| 展示時的使用者流程 | 待填 |
| 優先展示的 recipe ID（seed-01／02／03） | 待填 |
| 結果模式：即時生成／事先生成／示意 | 待填 |
| 各成員負責的畫面與檔案 | 待填 |
| 共用資料與路徑版本、負責人 | 待填 |
| 整合者、展示操作者、簡報者 | 待填 |
| 決定時間與三位成員確認 | 待填 |

**範圍原則：每增加一項工作，須刪減一項相近工作量的項目。** 本表用於確定 prototype 做法；專案目標已記錄於 PROJECT.md。

## 建議分工（以現場決策為準）

| 角色 | 暫定責任 | 第一個可交付成果 |
|---|---|---|
| A：視覺與體驗 | Gallery：呈現預覽、標題與原作者，並連結至對應 recipe | 至少一張可進入 Recipe 的卡片；缺少預覽圖時顯示文字與來源連結 |
| 專案提案者：Recipe 與內容 | Recipe：呈現原貼文、已核對的原作者 IG、prompt、輸入說明與試用入口 | 一份資料正確的 Recipe，能連至同 ID 的 Create |
| B：技術與 AI 串接 | Create、生成串接、Result、備案與執行環境 | 可用照片與對應 prompt 取得結果；失敗時有清楚狀態與備案 |

三個區塊使用相同的 recipe ID 與資料欄位（見 CREATIVE-RECIPE.md）。若採用四個路徑，可使用 `/` → `/recipe/:recipeId` → `/create/:recipeId` → `/result/:resultId`；實際路徑由團隊決定。每個共用檔案指定一位維護者，欄位變更須先同步給其他成員。

## 90 分鐘參考時程

`T` 為決策完成、開始開發的時間。若活動時程不同，應先保留整合檢查與彩排時間，再調整各階段長度。

| 時間 | 工作 | 驗收重點 |
|---|---|---|
| T+0～30 | 建立最小可執行版本；各角色完成負責區塊的基本功能 | 優先展示的 recipe 資料與連結可用 |
| **T+30｜Checkpoint 1** | 整合並走完入口至 Result 的主要流程 | 若流程中斷，立即縮減範圍或採用備案 |
| T+35～60 | 改善已選定流程，穩定生成串接 | 原作者連結、prompt 與圖片對應正確 |
| **T+60｜Checkpoint 2** | 在展示環境測試完整流程、窄螢幕與生成失敗狀態 | 即時生成或備案均可如實展示 |
| **T+65｜Feature freeze** | 停止新增功能與依賴 | 之後僅處理整合、錯誤、嚴重畫面問題與展示準備 |
| T+65～80 | 固定展示版本，測試正常與失敗路徑 | 單次 API 失敗不致中斷展示 |
| T+80～87 | 計時彩排 | 說明與實際功能一致，符合活動時間限制 |
| **T+87｜Hands off** | 停止修改，保留已驗證版本 | 完成展示準備 |

## 備案與啟用條件

| 狀況 | 處理方式 |
|---|---|
| 原作者預覽圖無法展示 | 使用文字卡與原始貼文連結；不以未核實圖片代替原作 |
| 原作者 IG 尚未核對 | 僅提供原始貼文連結，暫不顯示 IG 入口 |
| 優先展示的 prompt 無法執行 | 改用另一份已測試的 seed；若調整 prompt，須保留原文並標註執行版本 |
| 生成 API 出錯或超時 | 顯示錯誤狀態並切換預備結果；若非本次上傳照片產生，須在畫面明示 |
| Gallery 或整合未完成 | 從已完成的 Recipe 頁進行展示，保留上一個可用版本 |
| 無法部署 | 採用已驗證的本機展示方式，保留彩排時間 |

## 展示前檢查

- [ ] 原貼文、原作者與 IG 資訊已核對一致；未核對資料未標示為已確認。
- [ ] 預覽圖、prompt、測試照片與備用結果各有來源紀錄；缺少預覽圖時仍可理解內容。
- [ ] 平台內試用確實帶入所選 recipe 的 prompt；若生成尚未接通，示意流程已明確標示。
- [ ] Result 清楚標示即時生成、事先生成或示意模式，並保留原作者來源。
- [ ] 正常流程、生成失敗流程及完整計時彩排均已完成。

---

# 專案設計規劃

## 文件狀態

- **狀態：** Proposed
- **適用範圍：** Build Day prototype
- **Figma 參考節點：** [mosAIc Recipe Detail｜5:142](https://www.figma.com/design/b79P5kNBD1ntjyoyAjER0P/mosAIc?node-id=5-142)
- **產品範圍來源：** [PROJECT.md](PROJECT.md) 與 [CREATIVE-RECIPE.md](CREATIVE-RECIPE.md)
- **內容資料來源：** [SEED-RECIPES.md](SEED-RECIPES.md)

Figma 用於決定資訊排列與視覺方向，不自動成為後端需求。Figma 與產品文件衝突時，先由團隊做產品決策，再修改資料契約。

## Goals

1. 同一個 repository 管理 Python backend、website 與 mobile。
2. Website 與 mobile 共用 API client 和 TypeScript contract，不共用 UI 元件。
3. 使用者只傳 `recipeId` 和圖片；prompt 由 backend 查找並送給生成服務。
4. 所有結果明確標示 `live`、`cached` 或 `mock`，不把預備素材冒充本次生成。
5. 一份 recipe 資料同時支援 Gallery、Recipe、Create 和 Result。

## Non-Goals

- 帳號、登入與權限管理。
- Favorites、My Recipes、Community 與 Creator submission。
- 分享紀錄、商業授權管理與 AI training permission workflow。
- Creative Context 自動生成或藝術家相似度分析。
- Database、Redis、job queue、Docker、Kubernetes 與 production multi-instance deployment。

## 目標 Monorepo 目錄

> 以下為目標結構；目前檔案尚未搬移。搬移時須以小步 commit 進行，不能同時改行為。

```text
ai-creative-playground/
├── backend/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py
│   │   ├── generation.py
│   │   └── recipes.py
│   ├── data/
│   │   └── recipes.json
│   ├── scripts/
│   │   └── pregen.py
│   ├── storage/
│   │   ├── seed/
│   │   │   └── .gitkeep
│   │   ├── fallback/
│   │   │   └── .gitkeep
│   │   └── results/
│   │       └── .gitkeep
│   ├── tests/
│   │   ├── __init__.py
│   │   ├── test_generation.py
│   │   └── test_api.py
│   ├── .env.example
│   ├── .gitignore
│   └── requirements.txt
│
├── frontend/
│   ├── website/
│   │   ├── app/
│   │   │   ├── create/
│   │   │   │   └── [id]/
│   │   │   │       └── page.tsx
│   │   │   ├── recipe/
│   │   │   │   └── [id]/
│   │   │   │       └── page.tsx
│   │   │   ├── result/
│   │   │   │   └── [id]/
│   │   │   │       └── page.tsx
│   │   │   ├── globals.css
│   │   │   ├── layout.tsx
│   │   │   └── page.tsx
│   │   ├── components/
│   │   │   ├── create/
│   │   │   ├── gallery/
│   │   │   ├── recipe/
│   │   │   ├── result/
│   │   │   └── shared/
│   │   ├── public/
│   │   │   ├── icons/
│   │   │   └── images/
│   │   ├── tests/
│   │   ├── .env.local.example
│   │   ├── next.config.ts
│   │   ├── package.json
│   │   ├── tsconfig.json
│   │   └── README.md
│   │
│   ├── mobile/
│   │   ├── app/
│   │   │   ├── create/
│   │   │   │   └── [id].tsx
│   │   │   ├── recipe/
│   │   │   │   └── [id].tsx
│   │   │   ├── result/
│   │   │   │   └── [id].tsx
│   │   │   ├── _layout.tsx
│   │   │   └── index.tsx
│   │   ├── assets/
│   │   │   ├── icons/
│   │   │   └── images/
│   │   ├── components/
│   │   │   ├── create/
│   │   │   ├── gallery/
│   │   │   ├── recipe/
│   │   │   ├── result/
│   │   │   └── shared/
│   │   ├── tests/
│   │   ├── .env.example
│   │   ├── app.json
│   │   ├── package.json
│   │   ├── tsconfig.json
│   │   └── README.md
│   │
│   └── shared/
│       ├── api/
│       │   └── client.ts
│       ├── config/
│       │   └── environment.ts
│       ├── types/
│       │   ├── generation.ts
│       │   └── recipe.ts
│       ├── package.json
│       └── tsconfig.json
│
├── docs/
│   ├── build-day/
│   │   ├── BUILD-DAY.zh-TW.md
│   │   ├── Buildday_prompt.md
│   │   ├── CREATIVE-RECIPE.md
│   │   ├── PROJECT.md
│   │   ├── SEED-RECIPES.md
│   │   └── WIREFRAMES.zh-TW.md
│   └── backend-architecture.html
│
├── scripts/
│   ├── dev.sh
│   └── test.sh
│
├── .gitignore
├── package.json
├── pnpm-workspace.yaml
└── README.md
```

## 目錄責任

| 目錄 | Owner | 責任 |
|---|---|---|
| `backend/` | Backend / AI | Recipe public projection、prompt lookup、圖片驗證、生成、fallback、result storage |
| `frontend/website/` | Website | Next.js Gallery、Recipe、Create、Result |
| `frontend/mobile/` | Mobile | Expo / React Native Gallery、Recipe、Create、Result |
| `frontend/shared/` | Frontend shared | API client、environment config、TypeScript contract；不放平台專屬 UI |
| `docs/` | Team | 產品範圍、資料定義、架構決策與 Build Day 執行計畫 |

## 系統資料流

```text
Website ── same-origin /api/* rewrite ──┐
                                        ├── FastAPI backend
Mobile ── API_BASE_URL ─────────────────┘
                                             │
                                             ├── recipes.json
                                             ├── image generation provider
                                             └── storage/{seed,fallback,results}
```

```text
Gallery / Recipe
  → GET /api/recipes 或 GET /api/recipes/{recipeId}

Create
  → POST /api/generate
    multipart: recipeId + image
    → backend 查 prompt
    → provider 成功：live
    → provider 失敗且有 fallback：cached
    → 沒有 fallback：mock

Result
  → GET /api/results/{resultId}
```

## Recipe 資料所有權

`backend/data/recipes.json` 是唯一真實來源。Website 與 mobile 不直接打包完整 JSON，改由 backend 回傳 public projection，避免 prompt 意外進入 client bundle。

最小 backend record：

```ts
type RecipeRecord = {
  id: string;
  title: string;
  summary: string;
  sourcePostUrl: string;
  creatorName: string | null;
  creatorInstagramUrl: string | null;
  previewImageUrl: string | null;
  previewUseBasis: string | null;
  inputNote: string;
  prompt: string;
  promptUseBasis: string | null;
  creatorChecked: boolean;
  tryReady: boolean;
};
```

Public API 不回傳：

- `prompt`
- `promptUseBasis`
- 其他僅供 backend 執行或稽核的欄位

`promptVisibility` 暫不加入。當前三份 seed 都是公開 prompt；若產品之後真的支援 private prompt，再新增欄位與對應測試。

## API Contract

### Recipe

```text
GET /api/recipes
  → 200 { recipes: PublicRecipe[] }

GET /api/recipes/{recipeId}
  → 200 PublicRecipe
  → 404 { error: "unknown_recipe" }
```

`PublicRecipe`：

```ts
type PublicRecipe = {
  id: string;
  title: string;
  summary: string;
  sourcePostUrl: string;
  creatorName: string | null;
  creatorInstagramUrl: string | null;
  previewImageUrl: string | null;
  inputNote: string;
  tryReady: boolean;
};
```

### Generation

```text
GET /api/health
  → 200 { ok: true }

POST /api/generate
  multipart/form-data
  recipeId: string
  image: jpeg | png | webp，<= 8MB

  → 200 { resultId }
  → 400 { error: "missing_recipe_id" | "missing_image" | "unsupported_type" | "too_large" }
  → 403 { error: "recipe_not_ready" }
  → 404 { error: "unknown_recipe" }

GET /api/results/{resultId}
  → 200 GenerationResult
  → 404 { error: "unknown_result" }
```

Website 以相對路徑呼叫 `/api/*`；mobile 透過 `frontend/shared/api/client.ts` 注入 `API_BASE_URL`。`imageUrl` 保持相對路徑，shared client 在 mobile 端補上 backend base URL。

## GenerationResult 不變量

1. `mode: "live"` 代表 provider 回傳的 bytes 已通過圖片 magic bytes 驗證。
2. `mode: "cached"` 代表 fallback 圖片與 provenance sidecar 都有效，而且不是本次上傳照片生成。
3. `mode: "mock"` 時 `imageUrl` 必須是 `null`。
4. `sourceNote` 由 backend 產生，website 與 mobile 原樣顯示。
5. 使用者上傳圖片不寫入 `storage/`；只保存生成結果與已核實的 fallback。

## 根據 Figma 需要修改的後端設計

### 必做

| Figma／產品需求 | 現況 | 後端調整 |
|---|---|---|
| Website 與 mobile 都要顯示 Recipe | 現在只有 root JSON，前端尚未建立 | 增加 `GET /api/recipes` 與 `GET /api/recipes/{id}`，回傳 public projection |
| Creator 不可被編造 | 三份 seed 的 creator 仍未核實 | `creatorName`、IG 保持 nullable；未核實只回原貼文 URL |
| Before / After 預覽 | 實際 JSON 沒有 preview 欄位 | 增加 `previewImageUrl` 與 `previewUseBasis`；沒有使用依據時回 `null` |
| Try permission | Figma 顯示可試用，但 backend 只檢查 recipe 是否存在 | 增加 `tryReady`，`POST /api/generate` 必須拒絕未準備完成的 recipe |
| Result 不可冒充 live | 已有 `live/cached/mock` | 保留現有設計；補上 cached 圖片 magic bytes 驗證 |

### Figma 必須修正或刪除

| Figma 畫面 | 決策 |
|---|---|
| `Prompt kept private by creator` | 當前三份 prompt 是公開內容，改為顯示公開 prompt 或依產品決策隱藏整區 |
| `Share result` 顯示允許 | 沒有核實的 permission，不顯示允許狀態 |
| Commercial use / AI training | Prototype 不建立權限系統；隱藏或明確顯示 unknown |
| Creative Context 與藝術家名稱 | 本階段移除；若之後加入，必須標示 creator / curator / AI suggestion 來源 |
| Favorites、My Recipes、Community、Create Your Own | 本階段移除或 disable，不新增 backend endpoint |

### 內容矛盾

- Figma 的 About 寫有 `sharp typography`，但 `seed-01` 明確要求輸出不得包含任何文字。
- Figma 顯示 creator 名稱與社群資料，但目前 source 尚未核實。
- Figma 顯示 Try 與 Share 已允許，但目前沒有 permission evidence。
- Figma 的 Creative Context 未區分創作者資訊、策展資訊與 AI 推測。

## Provider 決策

目前 `_call_provider()` 尚未實作，但 `.env.example` 已使用 `ANTHROPIC_API_KEY`；兩者不能視為已完成 provider 選型。

Build Day 前必須完成：

1. 選定一個支援 image + prompt → image 的 provider。
2. 依 provider 官方文件實作 `_call_provider()`，不建立單一實作的 adapter interface。
3. 使用同一條 provider path 執行三份 `pregen.py`。
4. 記錄 provider、model、生成時間、測試照片與 duration。
5. 若 pregen 未成功，當天不啟用 live，只展示 cached 或 mock。

## 儲存與部署邊界

Prototype 使用單一 FastAPI process 和本機檔案系統：

```text
backend/storage/seed/       已核實的 recipe 預覽素材
backend/storage/fallback/   預先生成結果與 provenance sidecar
backend/storage/results/    本次執行產生的 result JSON 與圖片
```

只有在下列任一條件成立時才升級架構：

- 部署到無持久檔案系統的 serverless runtime。
- 同時執行多個 backend instance。
- 生成請求超過 HTTP timeout。
- 需要跨裝置永久保存使用者結果。

升級方向才是 object storage + result database + async job；目前不建置。

## Migration Plan

### Phase 1｜只搬目錄，不改行為

- `backend/main.py` → `backend/app/main.py`
- `backend/generate.py` → `backend/app/generation.py`
- `backend/pregen.py` → `backend/scripts/pregen.py`
- `data/recipes.json` → `backend/data/recipes.json`
- 更新 import、測試路徑和 `dev.sh`

### Phase 2｜建立 shared contract

- 建立 `frontend/shared/types/recipe.ts`
- 建立 `frontend/shared/types/generation.ts`
- 建立可注入 base URL 的 `frontend/shared/api/client.ts`
- 增加 recipe read endpoints 與 `tryReady` enforcement

### Phase 3｜建立 website

- 建立 Next.js app
- 完成 Gallery → Recipe → Create → Result
- 驗證 rewrite、loading、error 與三種 result mode

### Phase 4｜建立 mobile

- 建立 Expo app
- 重用 shared API client 和 types
- 驗證實機 API base URL、圖片上傳、結果圖片 URL 與 navigation

## 驗收條件

- [ ] Website 與 mobile 使用同一份 public recipe contract。
- [ ] Client payload 不包含 prompt。
- [ ] 未核實 creator 不顯示虛構名稱或 IG。
- [ ] `tryReady=false` 的 recipe 無法呼叫 provider。
- [ ] 上傳格式、8MB 限制與 magic bytes 驗證均有效。
- [ ] `live`、`cached`、`mock` 三種結果在兩個 client 都能正確呈現。
- [ ] Cached sidecar 缺失、圖片損壞或 provider 失敗時不冒充 live。
- [ ] Website 經 rewrite 呼叫；mobile 經 `API_BASE_URL` 呼叫。
- [ ] Backend unit tests 與 HTTP contract tests 通過。
- [ ] 完整 demo 不依賴現場 provider 成功。
