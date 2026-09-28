import type { PublicRecipe } from "./recipe";

// Shared contract with the FastAPI backend. Changing a field here means changing
// backend/generate.py in the same breath.

/** How the result was produced. Always present. Never inferred on the client. */
export type ResultMode = "live" | "cached" | "mock";

export type GenerationResult = {
  resultId: string;
  recipeId: string;
  mode: ResultMode;
  /**
   * Server-authored disclosure. Render VERBATIM — do not paraphrase, summarise, or
   * replace it with UI copy. It is the one thing stopping the page from claiming a
   * cached image was made from the user's photo.
   */
  sourceNote: string;
  /** null exactly when mode === 'mock'. Show the layout and the note, minus the image. */
  imageUrl: string | null;
  /** Debug only — why live was skipped. null when mode === 'live'. Do not display. */
  fallbackReason: string | null;
  recipeTitle: string;
  creatorName: string | null;
  sourcePostUrl: string;
  creatorInstagramUrl: string | null;
  /** ISO 8601 UTC, e.g. "2026-09-28T09:30:00Z" */
  createdAt: string;
};

export type ApiError =
  | "missing_recipe_id"
  | "missing_image"
  | "unsupported_type"
  | "too_large"
  /** 403 — recipe.tryReady is false. Not a user error; the recipe is not cleared yet. */
  | "recipe_not_ready"
  | "unknown_recipe"
  | "unknown_result";

/** GET /api/recipes */
export type RecipeListResponse = { recipes: PublicRecipe[] };

/** POST /api/generate — multipart: recipeId + image. jpeg/png/webp, <= 8MB. */
export type GenerateResponse = { resultId: string } | { error: ApiError };

/** GET /api/health — distinguishes "backend not running" from a real error. */
export type HealthResponse = { ok: true };
