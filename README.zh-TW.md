# mosAIc

**用你自己的照片，試試創作者分享的 AI 生圖 prompt，同時記得是誰做的。**

[English](README.md)

社群上的創作者常花很多時間反覆測試、調整圖片生成 prompt 才分享出來。mosAIc 把這些 prompt 整理成一份份「recipe」放在同一個畫廊：挑一份 recipe、看完整 prompt 與原始貼文、上傳一張照片，mosAIc 就幫你跑這份 prompt。不用複製文字、不用切換 AI 工具，每份 recipe 和每張結果都會連回原作者。

![mosAIc 操作示範：瀏覽 recipe、打開一份、上傳照片、查看結果](docs/media/walkthrough.gif)

<sub>此示範在本機錄製：暫時開放其中一份 recipe 試用，且未設定 AI 金鑰，所以結果頁如實顯示「示意結果」。</sub>

## Demo 影片

> 🎬 **含即時 AI 生成的完整 Demo 影片：即將推出。**

## 怎麼用

1. **探索**：瀏覽 recipe、依風格篩選，可收藏在這台裝置。
2. **看 recipe**：完整 prompt、要上傳什麼照片、原始貼文與原作者連結。
3. **試用**：上傳一張 JPEG / PNG / WebP（最大 8MB），按 Create。
4. **看結果**：下載或分享圖片；頁面一定會標示這張圖怎麼來的，以及 prompt 是誰分享的。

## 特色

- **創作者優先**：每份 recipe 都連到原始貼文；原作者 IG 核對後才顯示。未核對時顯示「來源待確認」，不亂猜。
- **一鍵試用**：伺服器把你的照片和 recipe 存好的 prompt 一起送給生圖模型，瀏覽器不會接觸金鑰，也不會送出 prompt。
- **結果誠實標示**：`live`（剛剛用你的照片生成）、`cached`（事先用測試照片做的範例）、`mock`（示意）。不會把範例說成你的作品。
- **不保存照片**：mosAIc 只把照片轉給生圖模型，不會存下來。
- **結果可分享、預設不公開**：每張結果都有一個難以猜測的專屬連結，重新整理也還在；不會公開列出，只有你分享才會被看到，30 天後失效。
- **內建使用上限**：每人每分鐘、每天的次數上限、每日花費上限，以及重複點擊不重複扣費，避免免費試用被濫用。

## 本機執行

需要 Node.js 24+、pnpm 11、Python 3.10+，指令都在 repo 根目錄執行：

```sh
pnpm install
python3 -m venv apps/backend/.venv
apps/backend/.venv/bin/pip install -r apps/backend/requirements.txt
cp apps/backend/.env.example apps/backend/.env   # 填入 GEMINI_API_KEY
bash scripts/dev.sh
```

打開 http://localhost:3000。沒有金鑰也能跑，結果會標示為 `cached` 或 `mock`。要開放某份 recipe 試用，把 `apps/backend/data/recipes.json` 裡的 `tryReady` 改成 `true`。

全部測試：`bash scripts/test-all.sh`。部署設定、測試細節與專案結構請見 [英文 README](README.md) 與 [發佈清單](docs/release/v0.1-release-checklist.md)。

## 團隊

[@joojoohappy](https://github.com/joojoohappy)、[@ZoeWTY](https://github.com/ZoeWTY)
