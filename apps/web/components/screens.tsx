"use client";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import type { FormEvent, DragEvent } from "react";
import { mosaicApi, MosaicApiError, messageFor } from "@mosaic/api";
import { validateImage } from "@mosaic/core";
import { useApiData, useFavorites } from "./hooks";
import {
  Attribution,
  Back,
  categories,
  DataState,
  Icon,
  Panel,
  Placeholder,
  recipeTags,
  Shell,
  Tags,
} from "./ui";

const listRecipes = (_id: string) => mosaicApi.listRecipes();

export function Discover({
  savedOnly = false,
  community = false,
}: {
  savedOnly?: boolean;
  community?: boolean;
}) {
  const { data, error, loading, retry } = useApiData("recipes", listRecipes);
  const [category, setCategory] = useState("All");
  const { ids, ready } = useFavorites();
  const recipes = data?.filter(
    (r) =>
      (!savedOnly || ids.includes(r.id)) &&
      (category === "All" || recipeTags(r).includes(category)),
  );
  return (
    <Shell>
      <main className="body discover">
        <section className="hero">
          <h1>
            {savedOnly
              ? "Your favorite creative AI recipes"
              : "Explore creative AI recipes from the community"}
          </h1>
          <p>
            {savedOnly
              ? "Recipes you saved on this device."
              : "Browse prompts, styles, and techniques shared by creators."}
          </p>
        </section>
        <section className="categories">
          <h2>Categories</h2>
          <div className="chips">
            {categories.map((c) => (
              <button
                key={c}
                className="chip"
                aria-pressed={category === c}
                onClick={() => setCategory(c)}
              >
                {c}
              </button>
            ))}
          </div>
        </section>
        <section className="featured">
          <h2>
            {savedOnly
              ? "My Recipes"
              : community
                ? "Community Recipes"
                : "Featured Community Recipes"}
          </h2>
          {loading || (savedOnly && !ready) ? (
            <DataState loading />
          ) : error ? (
            <DataState error={error} retry={retry} />
          ) : (
            <div className="recipe-grid">
              {recipes?.map((r) => (
                <article className="recipe-card" key={r.id}>
                  <Link
                    className="card-link"
                    href={`/recipe/${encodeURIComponent(r.id)}`}
                    aria-label={r.title}
                  >
                    {r.previewImageUrl ? (
                      <div className="card-image">
                        <img src={r.previewImageUrl} alt={r.title} />
                      </div>
                    ) : (
                      <Placeholder
                        label="Recipe Thumbnail"
                        className="card-image"
                      />
                    )}
                    <div className="card-content">
                      <h3>{r.title}</h3>
                      <p>
                        {r.creatorName ? `by ${r.creatorName}` : "來源待確認"}
                      </p>
                      <Tags tags={recipeTags(r)} />
                    </div>
                  </Link>
                </article>
              ))}
              {recipes?.length === 0 && (
                <p className="empty">
                  {savedOnly
                    ? "這個分類尚無已收藏的 recipe。"
                    : "這個分類目前沒有 recipe。"}
                </p>
              )}
            </div>
          )}
        </section>
      </main>
    </Shell>
  );
}

export function RecipeDetail({ id }: { id: string }) {
  const {
    data: r,
    loading,
    error,
    retry,
  } = useApiData(id, mosaicApi.getRecipe);
  const { ids, toggle, ready } = useFavorites();
  const [notice, setNotice] = useState("");
  async function share() {
    try {
      await navigator.clipboard.writeText(window.location.href);
      setNotice("連結已複製");
    } catch {
      setNotice("請複製瀏覽器網址分享這份 recipe。");
    }
  }
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
                <Panel title="BEFORE → AFTER" className="comparison">
                  <div className="comparison-row">
                    <Placeholder
                      label="Original"
                      className="comparison-image"
                    />
                    <span className="comparison-arrow">
                      <Icon name="f530f" size={10} />
                    </span>
                    {r.previewImageUrl ? (
                      <div className="comparison-image placeholder">
                        <img
                          className="preview-content"
                          src={r.previewImageUrl}
                          alt="Recipe preview"
                        />
                      </div>
                    ) : (
                      <Placeholder
                        label="Generated"
                        className="comparison-image"
                      />
                    )}
                  </div>
                </Panel>
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
                    原始來源與創作者資訊以已核實資料為準。
                  </p>
                  <Attribution {...r} />
                </Panel>
                <Panel title="PERMISSIONS">
                  <div className="permission-row">
                    <span>Try with your image</span>
                    <span>{r.tryReady ? "已開放試用" : "尚未開放"}</span>
                  </div>
                  <p className="body-copy">
                    {r.tryReady
                      ? "請依原始貼文的使用條件與署名要求使用。"
                      : "這份 recipe 尚未開放試用"}
                  </p>
                  <Attribution {...r} />
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
                  <span className="private-prompt">
                    🔒 Prompt kept private by creator
                  </span>
                </Panel>
                <Panel title="CREATIVE CONTEXT">
                  <Tags tags={recipeTags(r)} />
                  <p className="body-copy">{r.inputNote}</p>
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

export function Create({ id }: { id: string }) {
  const {
    data: r,
    loading,
    error,
    retry,
  } = useApiData(id, mosaicApi.getRecipe);
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<string | null>(null);
  const [issue, setIssue] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [notReady, setNotReady] = useState(false);
  const [dragging, setDragging] = useState(false);
  const submitLock = useRef(false);
  const mounted = useRef(true);
  const input = useRef<HTMLInputElement>(null);
  const router = useRouter();
  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
    };
  }, []);
  useEffect(() => {
    if (!file) {
      setPreview(null);
      return;
    }
    const url = URL.createObjectURL(file);
    setPreview(url);
    return () => URL.revokeObjectURL(url);
  }, [file]);
  function choose(candidate: File | null) {
    if (busy || !available) return;
    const reason = validateImage(candidate);
    if (reason) {
      setFile(null);
      setIssue(messageFor(new MosaicApiError(reason)));
      return;
    }
    setFile(candidate);
    setIssue(null);
  }
  function drop(e: DragEvent) {
    e.preventDefault();
    setDragging(false);
    if (e.dataTransfer.files.length > 1) {
      setIssue("一次請選擇一張照片");
      return;
    }
    choose(e.dataTransfer.files[0] || null);
  }
  async function submit(e: FormEvent) {
    e.preventDefault();
    if (submitLock.current || !r || !r.tryReady || notReady) return;
    const reason = validateImage(file);
    if (reason || !file) {
      setIssue(messageFor(new MosaicApiError(reason || "missing_image")));
      return;
    }
    submitLock.current = true;
    setBusy(true);
    setIssue(null);
    try {
      const resultId = await mosaicApi.generate(r.id, file);
      if (mounted.current) router.push(`/result/${resultId}`);
    } catch (err) {
      if (mounted.current) {
        if (err instanceof MosaicApiError && err.code === "recipe_not_ready") {
          setNotReady(true);
          setIssue(null);
        } else setIssue(messageFor(err));
      }
    } finally {
      submitLock.current = false;
      if (mounted.current) setBusy(false);
    }
  }
  const available = Boolean(r?.tryReady && !notReady);
  return (
    <Shell>
      <main className="body">
        <Back href={`/recipe/${encodeURIComponent(id)}`}>
          {r?.title || "Back to Recipe"}
        </Back>
        {loading ? (
          <DataState loading />
        ) : error ? (
          <DataState error={error} retry={retry} />
        ) : (
          r && (
            <>
              <div className="create-title">
                <h1>Try this Recipe with your own image.</h1>
                <p>
                  Upload a photo and mosAIc will generate a new interpretation
                  using the selected prompt.
                </p>
              </div>
              <form
                className="create-layout"
                onSubmit={submit}
                aria-busy={busy}
              >
                <div className="form-left">
                  <input
                    ref={input}
                    id="image-upload"
                    type="file"
                    accept="image/jpeg,image/png,image/webp"
                    disabled={!available || busy}
                    aria-label="Upload image"
                    onChange={(e) => {
                      choose(e.target.files?.[0] || null);
                      e.target.value = "";
                    }}
                    hidden
                  />
                  <button
                    type="button"
                    className={`upload-area ${dragging ? "drag" : ""}`}
                    disabled={!available || busy}
                    onClick={() => input.current?.click()}
                    onDragOver={(e) => {
                      e.preventDefault();
                      if (available && !busy) setDragging(true);
                    }}
                    onDragLeave={() => setDragging(false)}
                    onDrop={drop}
                  >
                    <Icon />
                    <strong>Upload image</strong>
                    <span>JPG / PNG / WEBP · 最大 8MB</span>
                  </button>
                  <Panel title="Uploaded preview">
                    {preview ? (
                      <div className="uploaded-image">
                        <img src={preview} alt="你選擇的照片" />
                      </div>
                    ) : (
                      <Placeholder className="uploaded-image" />
                    )}
                    {file && (
                      <div className="file-info">
                        <span>{file.name}</span>
                        <button
                          type="button"
                          className="text-button"
                          disabled={busy}
                          onClick={() => {
                            setFile(null);
                            setIssue(null);
                          }}
                        >
                          移除照片
                        </button>
                      </div>
                    )}
                  </Panel>
                  {issue && (
                    <p className="error-message" role="alert">
                      {issue}
                    </p>
                  )}
                </div>
                <div className="form-right">
                  <Panel title="Before creating">
                    <p className="body-copy">{r.inputNote}</p>
                    <p className="body-copy">
                      {available
                        ? "請尊重原始創作者的使用條件與署名要求。"
                        : "這份 recipe 尚未開放試用"}
                    </p>
                    <Attribution {...r} />
                  </Panel>
                  <div className="cta-block">
                    <button
                      type="submit"
                      className="button primary wide"
                      disabled={!available || busy}
                    >
                      {!available
                        ? "尚未開放試用"
                        : busy
                          ? "CREATING…"
                          : "CREATE"}
                    </button>
                  </div>
                  {busy && (
                    <Panel title="Creating your interpretation…">
                      <div
                        className="loading-line"
                        role="status"
                        aria-live="polite"
                      >
                        <span className="loading-icon">
                          <Icon name="ab50f" size={16} />
                        </span>
                        <p>Using: {r.title}</p>
                      </div>
                      <p className="body-copy">
                        生成可能需要最多 60 秒，請勿重複送出。
                      </p>
                    </Panel>
                  )}
                </div>
              </form>
            </>
          )
        )}
      </main>
    </Shell>
  );
}

export function Result({ id }: { id: string }) {
  const {
    data: r,
    loading,
    error,
    retry,
  } = useApiData(id, mosaicApi.getResult);
  const [notice, setNotice] = useState("");
  const [downloading, setDownloading] = useState(false);
  async function share() {
    try {
      await navigator.clipboard.writeText(window.location.href);
      setNotice("連結已複製");
    } catch {
      setNotice("請複製瀏覽器網址分享這份結果。");
    }
  }
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
