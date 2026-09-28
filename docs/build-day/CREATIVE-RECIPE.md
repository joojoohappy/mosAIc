# Creative Recipe｜這份文件的用途

**定位：資料格式。** 它定義「一份 prompt 收藏」應有哪些欄位、各畫面如何讀同一筆資料。例如 `creator.instagramUrl` 是欄位名稱，不是已找到的 IG。你選的三份實際 prompt、Threads 連結和待補資訊，放在 [SEED-RECIPES.md](SEED-RECIPES.md)。



## 這次要做的產品體驗

整理社群媒體上創作者已公開分享的作品與 prompt，讓使用者在一個平台內：

1. 看原作者提供的**生成圖預覽**與作品簡介。
2. 按一下就**前往原作者 IG**；作品原始貼文也有獨立連結。
3. 選擇自己的照片，直接在平台內用該 prompt 嘗試生成；平台負責把照片和 prompt 交給選定的生成服務，使用者不用自己複製文字再切到另一個 AI 工具。
4. 在結果中看見這次使用了哪份 recipe、原作者是誰，以及結果是即時生成還是示範素材。

目前的主軸是 **curation + creator discovery + integrated try**。這份文件讓 Gallery、Recipe、Create/Result 三位 builder 使用同一筆資料、同一個 ID 和相同的署名資訊。它不是完整產品需求，也不要求這次完成投稿、remix、商用授權系統、AI training 設定、藝術史分析或審核平台。

## 一筆 recipe 的最小資料

以下為可直接轉成 TypeScript／JSON 的**概念欄位**，不是已定下的程式語言。

```ts
type SeedRecipe = {
  id: string;                 // 例如 "seed-01"，跨畫面保持不變
  title: string;              // 方便使用者辨認的暫定名稱
  summary: string;            // 一句話說明預期效果
  sourcePostUrl: string;      // 原始社群貼文，不等於 IG 個人頁
  creator: {
    displayName: string | null;
    instagramUrl: string | null;  // 核對後才顯示「前往原作者 IG」
  };
  previewImage: {
    src: string;               // 原作者提供且可在此展示的預覽圖
    alt: string;
    useBasis: string;          // 如何確認可在 prototype 展示
  } | null;
  prompt: {
    text: string;              // 來源中的完整 prompt；不擅自改寫
    useBasis: string;          // 如何確認可在 prototype 收錄／執行
  };
  input: {
    kind: 'image';              // 這三份都是圖片輸入
    note: string;              // 例如一次一張、適用犬類等
  };
  readiness: {
    sourceChecked: boolean;
    creatorChecked: boolean;
    previewReady: boolean;
    tryReady: boolean;
  };
};
```

**最小必備資料**是 ID、名稱、原貼文、完整 prompt、適用輸入，以及各項待核對狀態。創作者名稱、IG 與預覽圖可以暫時缺席；不要填虛構資料。使用者若點「前往原作者 IG」，目標必須是已核對的原作者 IG。只有 Threads 連結時，先顯示「查看原始貼文」。

## 三個 builder 如何使用同一筆資料

| 畫面／負責區塊 | 從 recipe 讀什麼 | 要做到什麼 |
|---|---|---|
| Gallery | `id`, `title`, `summary`, `previewImage`, `creator` | 看預覽、看創作者、點入同一個 recipe ID |
| Recipe | 原貼文、creator IG、完整 prompt、輸入說明 | 讓使用者知道來源，並選擇「前往原作者 IG」或「用我的照片試試」 |
| Create / Result | `id`, `prompt.text`, 上傳圖片、creator 資訊 | 由平台代入 prompt 生成；顯示結果模式與原作者署名 |

暫定路徑：`/` → `/recipe/:recipeId` → `/create/:recipeId` → `/result/:resultId`。如果現場選了更好的呈現形式，可以一起修改路徑；**`recipeId` 在前後畫面一致**這個共用約定仍須保留或明確改版。

## 「一鍵使用 prompt」實際代表什麼

使用者在平台選圖後，平台把**該 recipe 的 prompt 原文＋使用者圖片**送到當天選定且實際可用的生成服務，再把回傳結果顯示在平台內。這需要一個可用的圖片生成介面／API、費用與存取方式；目前尚未選定或驗證。不要把「顯示 prompt」或「複製 prompt」當作已完成整合。

三份 prompt 都要求圖片輸入。第一、二份原文說多張照片要各自輸出；若 Build Day 只支援單張上傳，UI 應明示「一次一張」，送給模型的原 prompt 仍保留原文。第三份雖寫 `pet image`，後段明確指定 `dog's head`；prototype 先以狗的照片測試，不宣稱所有寵物都適用。

結果要區分：`live`（本次照片即時生成）、`cached`（事先以指定照片產生的結果）、`mock`（示意圖）。若不是從使用者這次上傳的照片生成，畫面要明說，不能顯示「你的照片生成完成」。

## 來源與署名的最小規則

- 每張卡保留**原始貼文連結**；IG 連結另填，不能從 Threads 短網址猜出帳號。
- 公開看到 prompt，不等於已確認可以把原作者的圖複製到平台展示，或代作者宣告 remix／商用／訓練權限。預覽圖與 prompt 的使用依據分開記。
- 在未確認原作者與 IG 前，顯示「來源待確認」與原貼文連結，不放假名字或錯誤 IG。未取得可展示的原圖時，可以先使用文字卡與來源連結。
- 結果至少寫「使用 [recipe 名稱]；原 prompt 來源：[原貼文]／原作者：[已核對名稱]」。這份署名描述來源，不表示原作者製作了使用者的結果。
- 三個 Threads 連結與 prompt 已由使用者提供，但貼文內容、原作者身分、IG、預覽圖及可用範圍尚未獨立核對。核對結果填回 SEED-RECIPES.md。


## 給團隊的採用檢查

- 三位 builder 使用同一份 seed IDs、prompt 原文和已核對的 creator／來源資訊。
- 能從預覽到原貼文；核對 IG 後能前往正確的原作者 IG。
- 「試用」真的把照片和 prompt 交給可用的生成流程；若當天無法完成，就以明確標示的 fallback 展示，不冒充即時生成。
- 預覽圖、prompt、測試照片與預備結果各自有來源紀錄。
- 沒有核實的欄位維持未核實，不自動填成可用或已授權。
