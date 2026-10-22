// Shared contract. This is the PUBLIC projection the backend returns — not the
// full record. Fetch it from GET /api/recipes; do not import data/recipes.json.
//
// public_recipe() in apps/backend/app/recipes.py is an allowlist, so a private
// field added later stays private by default. The prompt text is included only
// when the creator shared it publicly; the client never sends a prompt back.

export type PublicRecipe = {
  id: string;
  title: string;
  summary: string;
  sourcePostUrl: string;
  /** null until someone verifies the Threads post. Render "來源待確認", never a guess. */
  creatorName: string | null;
  creatorInstagramUrl: string | null;
  /** null until a preview image is cleared for display. Currently null for all seeds. */
  previewImageUrl: string | null;
  inputNote: string;
  /** Output aspect ratio the prompt asks for, e.g. "3:4". */
  aspectRatio: string | null;
  /** "hidden" means the creator did not publish the prompt; `prompt` is then null. */
  promptVisibility: "public" | "hidden";
  /** Full prompt text, exactly as the creator shared it. null when hidden. */
  prompt: string | null;
  /**
   * false = no basis has been established for running this prompt, so
   * POST /api/generate returns 403 recipe_not_ready.
   * Currently false for all three seeds — disable Try and say why.
   */
  tryReady: boolean;
};
