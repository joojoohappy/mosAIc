"use client";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import type { DragEvent, FormEvent } from "react";
import { mosaicApi, MosaicApiError, messageFor } from "@mosaic/api";
import { validateImage } from "@mosaic/core";
import { fitForUpload } from "../fit-upload";
import { useApiData } from "../hooks";
import {
  Attribution,
  Back,
  DataState,
  Icon,
  Panel,
  Placeholder,
  Shell,
} from "../ui";

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
  const [live, setLive] = useState<boolean | null>(null);
  const submitLock = useRef(false);
  const mounted = useRef(true);
  const input = useRef<HTMLInputElement>(null);
  const router = useRouter();
  useEffect(() => {
    mosaicApi.liveGeneration().then((value) => {
      if (mounted.current) setLive(value);
    });
  }, []);
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
      const resultId = await mosaicApi.generate(r.id, await fitForUpload(file));
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
                  {available && live === false && (
                    <p className="mode-notice" role="note">
                      目前為示範模式：尚未設定 AI
                      生成服務，結果會是預備範例或示意圖，不會由你這次上傳的照片生成。
                    </p>
                  )}
                  {available && (
                    <p className="consent">
                      按下 CREATE，代表你同意把這張照片送到 Google Gemini
                      生成圖片， 並同意<Link href="/terms">使用條款</Link>與
                      <Link href="/privacy">隱私說明</Link>。mosAIc
                      不會保存原始照片。
                    </p>
                  )}
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
