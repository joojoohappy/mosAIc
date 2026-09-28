import type { ApiError, GenerationResult, PublicRecipe } from "@mosaic/types";

export type ClientErrorCode =
  | ApiError
  | "backend_unavailable"
  | "request_timeout"
  | "invalid_response"
  | "request_failed";
const apiErrors: ApiError[] = [
  "missing_recipe_id",
  "missing_image",
  "unsupported_type",
  "too_large",
  "recipe_not_ready",
  "unknown_recipe",
  "unknown_result",
];
export class MosaicApiError extends Error {
  readonly code: ClientErrorCode;
  readonly status: number;
  constructor(code: ClientErrorCode, status = 0) {
    super(code);
    this.name = "MosaicApiError";
    this.code = code;
    this.status = status;
  }
}
export const errorMessages: Record<ClientErrorCode, string> = {
  missing_recipe_id: "未取得 recipe 資料，請返回探索頁重新選擇。",
  missing_image: "請先選一張照片",
  unsupported_type: "只支援 JPEG / PNG / WebP",
  too_large: "照片請小於 8MB",
  recipe_not_ready: "這份 recipe 尚未開放試用",
  unknown_recipe: "找不到這份 recipe",
  unknown_result: "結果不存在或連結已失效",
  backend_unavailable: "後端未啟動",
  request_timeout: "等待生成逾時，請稍後再試。",
  invalid_response: "後端回傳的資料格式不符，請稍後再試。",
  request_failed: "無法完成請求，請稍後再試。",
};
export function messageFor(error: unknown): string {
  return errorMessages[
    error instanceof MosaicApiError ? error.code : "request_failed"
  ];
}
const record = (value: unknown): value is Record<string, unknown> =>
  typeof value === "object" && value !== null && !Array.isArray(value);
const nullableString = (value: unknown) =>
  value === null || typeof value === "string";
export function isPublicRecipe(value: unknown): value is PublicRecipe {
  return (
    record(value) &&
    ["id", "title", "summary", "sourcePostUrl", "inputNote"].every(
      (k) => typeof value[k] === "string",
    ) &&
    ["creatorName", "creatorInstagramUrl", "previewImageUrl"].every((k) =>
      nullableString(value[k]),
    ) &&
    typeof value.tryReady === "boolean"
  );
}
export function isGenerationResult(value: unknown): value is GenerationResult {
  if (
    !record(value) ||
    ![
      "resultId",
      "recipeId",
      "sourceNote",
      "recipeTitle",
      "sourcePostUrl",
      "createdAt",
    ].every((k) => typeof value[k] === "string") ||
    !["creatorName", "creatorInstagramUrl", "imageUrl", "fallbackReason"].every(
      (k) => nullableString(value[k]),
    )
  )
    return false;
  return (
    /^[0-9a-f]{32}$/.test(value.resultId as string) &&
    (value.mode === "mock"
      ? value.imageUrl === null
      : (value.mode === "live" || value.mode === "cached") &&
        typeof value.imageUrl === "string" &&
        value.imageUrl.length > 0)
  );
}
export function createMosaicClient(
  options: { baseUrl?: string; fetch?: typeof fetch } = {},
) {
  const base = (options.baseUrl || "").replace(/\/$/, "");
  const transport = options.fetch || globalThis.fetch;
  async function health(): Promise<boolean> {
    try {
      const r = await transport(base + "/api/health", {
        cache: "no-store",
        signal: AbortSignal.timeout(5_000),
      });
      const value: unknown = await r.json();
      return r.ok && record(value) && value.ok === true;
    } catch {
      return false;
    }
  }
  async function request(
    path: string,
    init: RequestInit = {},
    timeout = 10_000,
  ): Promise<unknown> {
    let response: Response;
    try {
      response = await transport(base + path, {
        ...init,
        cache: "no-store",
        signal: AbortSignal.timeout(timeout),
      });
    } catch (error) {
      if (!(await health())) throw new MosaicApiError("backend_unavailable");
      if (
        error instanceof Error &&
        ["TimeoutError", "AbortError"].includes(error.name)
      )
        throw new MosaicApiError("request_timeout");
      throw new MosaicApiError("request_failed");
    }
    if (response.status >= 500 && !(await health()))
      throw new MosaicApiError("backend_unavailable", response.status);
    let payload: unknown;
    try {
      payload = await response.json();
    } catch {
      throw new MosaicApiError("invalid_response", response.status);
    }
    if (!response.ok) {
      const code =
        record(payload) && apiErrors.includes(payload.error as ApiError)
          ? (payload.error as ApiError)
          : "request_failed";
      throw new MosaicApiError(code, response.status);
    }
    return payload;
  }
  return {
    health,
    async listRecipes(): Promise<PublicRecipe[]> {
      const value = await request("/api/recipes");
      if (
        !record(value) ||
        !Array.isArray(value.recipes) ||
        !value.recipes.every(isPublicRecipe)
      )
        throw new MosaicApiError("invalid_response");
      return value.recipes;
    },
    async getRecipe(id: string): Promise<PublicRecipe> {
      const value = await request("/api/recipes/" + encodeURIComponent(id));
      if (!isPublicRecipe(value)) throw new MosaicApiError("invalid_response");
      return value;
    },
    async generate(recipeId: string, file: File): Promise<string> {
      if (!recipeId) throw new MosaicApiError("missing_recipe_id");
      const body = new FormData();
      body.append("recipeId", recipeId);
      body.append("image", file);
      const value = await request(
        "/api/generate",
        { method: "POST", body },
        75_000,
      );
      if (
        !record(value) ||
        typeof value.resultId !== "string" ||
        !/^[0-9a-f]{32}$/.test(value.resultId)
      )
        throw new MosaicApiError("invalid_response");
      return value.resultId;
    },
    async getResult(id: string): Promise<GenerationResult> {
      if (!/^[0-9a-f]{32}$/.test(id))
        throw new MosaicApiError("unknown_result", 404);
      const value = await request("/api/results/" + id);
      if (!isGenerationResult(value))
        throw new MosaicApiError("invalid_response");
      return value;
    },
  };
}
export const mosaicApi = createMosaicClient();
