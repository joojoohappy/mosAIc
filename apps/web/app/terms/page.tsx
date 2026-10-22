import type { Metadata } from "next";
import { LegalPage } from "@/components/legal";

export const metadata: Metadata = { title: "使用條款" };

export default function Terms() {
  return (
    <LegalPage title="使用條款" updated="2026-10-22">
      <p>
        使用 mosAIc
        即表示你同意以下條款。這是一個測試中的早期版本，內容可能隨時調整。
      </p>
      <h2>創作者與 prompt</h2>
      <ul>
        <li>
          每份 recipe 的 prompt 屬於分享它的原作者。mosAIc
          只負責整理、標示來源，讓你在這裡試用；
          不代表你取得重新發布、商業使用或其他權利。
        </li>
        <li>
          標示「來源待確認」的
          recipe，作者身分尚未核對。想進一步使用，請先到原始貼文詢問原作者。
        </li>
        <li>
          生成結果上的署名說明 prompt 的來源，不代表原作者製作或認可了你的結果。
        </li>
      </ul>
      <h2>你上傳的內容</h2>
      <ul>
        <li>只上傳你擁有或有權使用的照片；未經同意，不要上傳他人的照片。</li>
        <li>
          不得上傳違法、侵權、色情、暴力或騷擾性的內容，也不得用來冒充他人。
        </li>
      </ul>
      <h2>服務限制</h2>
      <ul>
        <li>
          為了控制成本與防止濫用，每人每天的生成次數與全站每日總量都有上限，達到上限時會暫停生成。
        </li>
        <li>
          AI
          生成的結果可能不準確或不如預期，服務以「現況」提供，不保證隨時可用。
        </li>
        <li>我們可能在不另行通知的情況下調整、暫停或移除 recipe 與功能。</li>
      </ul>
      <p>
        資料怎麼被處理，請看<a href="/privacy">隱私說明</a>。
      </p>
    </LegalPage>
  );
}
