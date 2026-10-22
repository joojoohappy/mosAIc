"use client";
import Link from "next/link";
import { mosaicApi } from "@mosaic/api";
import { useApiData, useFavorites, useShareLink } from "../hooks";
import {
  Attribution,
  Back,
  DataState,
  Icon,
  Panel,
  recipeTags,
  Shell,
  Tags,
} from "../ui";

export function RecipeDetail({ id }: { id: string }) {
  const {
    data: r,
    loading,
    error,
    retry,
  } = useApiData(id, mosaicApi.getRecipe);
  const { ids, toggle, ready } = useFavorites();
  const { notice, share, copy } = useShareLink(
    "請複製瀏覽器網址分享這份 recipe。",
  );
  return (
    <Shell>
      <main className="body">
        <div className="detail-nav">
          <Back />
          {r && (
            <div className="actions">
              <button
                className="button"
                disabled={!ready}
                aria-pressed={ids.includes(r.id)}
                onClick={() => toggle(r.id)}
              >
                {ids.includes(r.id)
                  ? "Saved to Favorites"
                  : "Save to Favorites"}
              </button>
              <button className="button" onClick={share}>
                Share
              </button>
            </div>
          )}
        </div>
        {notice && (
          <p role="status" className="notice">
            {notice}
          </p>
        )}
        {loading ? (
          <DataState loading />
        ) : error ? (
          <DataState error={error} retry={retry} />
        ) : (
          r && (
            <div className="detail-layout">
              <aside className="left-col">
                {r.previewImageUrl ? (
                  <Panel
                    title={r.previewBeforeUrl ? "BEFORE → AFTER" : "EXAMPLE"}
                    className="comparison"
                  >
                    <div className="comparison-row">
                      {r.previewBeforeUrl && (
                        <>
                          <div className="comparison-image placeholder">
                            <img
                              className="preview-content"
                              src={r.previewBeforeUrl}
                              alt="創作者使用的原始照片"
                            />
                          </div>
                          <span className="comparison-arrow">
                            <Icon name="f530f" size={10} />
                          </span>
                        </>
                      )}
                      <div className="comparison-image placeholder">
                        <img
                          className="preview-content"
                          src={r.previewImageUrl}
                          alt={`${r.title} 的創作者範例`}
                        />
                      </div>
                    </div>
                  </Panel>
                ) : (
                  <Panel title="EXAMPLE" className="comparison">
                    <p className="body-copy">
                      原作者的範例圖尚未取得授權展示，請到原始貼文查看。
                    </p>
                  </Panel>
                )}
                <Panel title="CREATOR">
                  <div className="creator-row">
                    <span className="avatar">
                      {r.creatorName ? r.creatorName.slice(0, 2) : "?"}
                    </span>
                    <div>
                      <strong>{r.creatorName || "來源待確認"}</strong>
                    </div>
                  </div>
                  <p className="body-copy">
                    {r.creatorName
                      ? "這份 prompt 由原作者分享；歡迎到原貼文與作者交流。"
                      : "原作者尚未核對，先提供原始貼文連結。"}
                  </p>
                  <Attribution {...r} hideName />
                </Panel>
                <Panel title="PERMISSIONS">
                  <div className="permission-row">
                    <span>Try with your image</span>
                    <span>{r.tryReady ? "已開放試用" : "尚未開放"}</span>
                  </div>
                  <p className="body-copy">
                    {r.tryReady
                      ? "請依原始貼文的使用條件與署名要求使用。"
                      : "原作者與使用依據核對完成前，這份 recipe 暫不開放試用。"}
                  </p>
                </Panel>
              </aside>
              <div className="right-col">
                <div className="title-block">
                  <h1>{r.title}</h1>
                  <Attribution {...r} />
                  <Tags tags={recipeTags(r)} />
                </div>
                <div className="design-rule">
                  <Icon name="20a5c" size={684} height={1} />
                </div>
                <Panel title="ABOUT">
                  <p className="body-copy">{r.summary}</p>
                </Panel>
                <Panel title="PROMPT">
                  {r.prompt ? (
                    <>
                      <pre
                        className="prompt-text"
                        tabIndex={0}
                        aria-label="Prompt 全文"
                      >
                        {r.prompt}
                      </pre>
                      <button
                        className="text-button"
                        onClick={() => copy(r.prompt!, "Prompt 已複製")}
                      >
                        複製 prompt
                      </button>
                    </>
                  ) : (
                    <span className="private-prompt">
                      🔒 創作者未公開這份 prompt
                    </span>
                  )}
                </Panel>
                <Panel title="HOW TO USE">
                  <p className="body-copy">{r.inputNote}</p>
                  {r.aspectRatio && (
                    <p className="body-copy">輸出比例：{r.aspectRatio}</p>
                  )}
                </Panel>
                <div className="cta-block">
                  {r.tryReady ? (
                    <Link
                      href={`/create/${encodeURIComponent(r.id)}`}
                      className="button primary wide"
                    >
                      TRY THIS RECIPE
                    </Link>
                  ) : (
                    <>
                      <button className="button primary wide" disabled>
                        尚未開放試用
                      </button>
                      <p className="readiness">這份 recipe 尚未開放試用</p>
                    </>
                  )}
                </div>
              </div>
            </div>
          )
        )}
      </main>
    </Shell>
  );
}
