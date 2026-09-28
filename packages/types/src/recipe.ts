// Shared contract. This is the PUBLIC projection the backend returns — not the
// full record. Fetch it from GET /api/recipes; do not import data/recipes.json.
//
// The backend never sends `prompt`. That used to be a convention ("only read the
// JSON in a server component"); it is now structural — public_recipe() in
// apps/backend/app/recipes.py is an allowlist, so a private field added later stays
// private by default.

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
  /**
   * false = no basis has been established for running this prompt, so
   * POST /api/generate returns 403 recipe_not_ready.
   * Currently false for all three seeds — disable Try and say why.
   */
  tryReady: boolean;
};
