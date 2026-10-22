"use client";
import Link from "next/link";
import { useState } from "react";
import { mosaicApi } from "@mosaic/api";
import { useApiData, useShareLink } from "../hooks";
import { Attribution, Back, DataState, Icon, Shell } from "../ui";

export function Result({ id }: { id: string }) {
  const {
    data: r,
    loading,
    error,
    retry,
  } = useApiData(id, mosaicApi.getResult);
  const { notice, setNotice, share } =
    useShareLink("請複製瀏覽器網址分享這份結果。");
  const [downloading, setDownloading] = useState(false);
  async function download() {
    if (!r?.imageUrl || downloading) return;
    setDownloading(true);
    try {
      const response = await fetch(r.imageUrl);
      if (!response.ok) throw new Error();
      const blob = await response.blob();
      if (!blob.type.startsWith("image/")) throw new Error();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `mosaic-${r.resultId}.${blob.type === "image/jpeg" ? "jpg" : blob.type === "image/webp" ? "webp" : "png"}`;
      a.click();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
    } catch {
      setNotice("圖片下載失敗，請稍後再試。");
    } finally {
      setDownloading(false);
    }
  }
  return (
    <Shell>
      <main className="body">
        <div className="detail-nav">
          <Back>Back to Home</Back>
          {r && (
            <div className="actions">
              <button
                className="button"
                disabled={!r.imageUrl || downloading}
                onClick={download}
              >
                {downloading ? "Downloading…" : "Download"}
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
            <div className="detail-layout result-layout">
              <div className="left-col">
                {r.imageUrl ? (
                  <div className="result-image">
                    <img src={r.imageUrl} alt={r.recipeTitle} />
                  </div>
                ) : (
                  <div className="empty-result">
                    <p>目前尚無生成圖片</p>
                  </div>
                )}
              </div>
              <div className="right-col">
                <div className="title-block">
                  <h1>
                    {r.mode === "live"
                      ? "YOUR CREATION"
                      : r.mode === "cached"
                        ? "預備結果"
                        : "示意結果"}
                  </h1>
                  <p className="created-with">
                    Created with{" "}
                    <Link href={`/recipe/${encodeURIComponent(r.recipeId)}`}>
                      {r.recipeTitle}
                    </Link>
                  </p>
                  <Attribution {...r} />
                </div>
                <div className="design-rule">
                  <Icon name="20a5c" size={684} height={1} />
                </div>
                <section
                  className={`disclosure disclosure-${r.mode}`}
                  aria-label="結果來源"
                >
                  <span className="mode-label">{r.mode}</span>
                  <p>{r.sourceNote}</p>
                </section>
                <div className="next-steps">
                  <div className="next-row">
                    <Link
                      href={`/create/${encodeURIComponent(r.recipeId)}`}
                      className="button wide"
                    >
                      再試一次
                    </Link>
                    <Link
                      href={`/recipe/${encodeURIComponent(r.recipeId)}`}
                      className="button wide"
                    >
                      返回 Recipe
                    </Link>
                  </div>
                  <p>Want to try another idea?</p>
                  <Link href="/" className="button primary wide">
                    EXPLORE MORE RECIPES
                  </Link>
                </div>
              </div>
            </div>
          )
        )}
      </main>
    </Shell>
  );
}
