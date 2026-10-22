import type { Metadata } from "next";
import { LegalPage } from "@/components/legal";

export const metadata: Metadata = { title: "隱私說明" };

export default function Privacy() {
  return (
    <LegalPage title="隱私說明" updated="2026-10-22">
      <p>
        mosAIc 不需要帳號，也不使用追蹤或廣告
        cookie。以下是你使用時，資料實際上怎麼被處理。
      </p>
      <h2>你上傳的照片</h2>
      <ul>
        <li>
          按下 Create 後，照片會和這份 recipe 的 prompt 一起送到 Google Gemini
          API 生成圖片。
        </li>
        <li>
          mosAIc 不會保存你上傳的原始照片：處理完這次請求就丟棄。Google 依其{" "}
          <a
            href="https://ai.google.dev/gemini-api/terms"
            target="_blank"
            rel="noopener noreferrer"
          >
            Gemini API 條款
          </a>{" "}
          處理收到的資料。
        </li>
        <li>請只上傳你有權使用的照片，避免上傳含有他人或敏感資訊的照片。</li>
      </ul>
      <h2>生成結果</h2>
      <ul>
        <li>
          生成的圖片與結果資訊（使用的
          recipe、時間）會被保存，讓你可以重新整理、下載或分享。
        </li>
        <li>
          每張結果都有一個隨機、難以猜測的連結。我們不會公開列出結果；但任何拿到連結的人都能看到，
          所以只有在你自己分享時才會被別人看見。
        </li>
        <li>
          結果連結會在 30
          天後失效。目前過期的檔案還不會自動刪除，之後的版本會加上定期清除；需要提早刪除請照下方方式聯絡我們。
        </li>
      </ul>
      <h2>其他資料</h2>
      <ul>
        <li>
          「收藏」只存在你這台裝置的瀏覽器（localStorage），不會傳到伺服器。
        </li>
        <li>
          為了防止濫用，伺服器會暫時用你的 IP
          位址計算使用次數（只在記憶體中，不另外保存）。
          託管服務商可能依其政策保留一般的連線紀錄。
        </li>
      </ul>
      <h2>聯絡</h2>
      <p>
        想刪除某張結果或有任何問題，請到{" "}
        <a
          href="https://github.com/joojoohappy/mosAIc/issues"
          target="_blank"
          rel="noopener noreferrer"
        >
          GitHub Issues
        </a>{" "}
        告訴我們（請勿公開貼出結果連結，說明大致時間與 recipe 即可）。
      </p>
    </LegalPage>
  );
}
