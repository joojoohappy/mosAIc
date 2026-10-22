# Product

## What mosAIc does

Creators on social media spend a long time testing and refining image-generation prompts before they share them. mosAIc gathers those prompts in one place so more people can find them, try them on their own photos, and go back to the original creator to talk about the work.

A visitor can:

1. Browse curated prompts ("recipes"), each with the creator's own preview image when one is cleared for display.
2. Open a recipe to read the full prompt, the original post, and, once verified, a one-click link to the creator's Instagram.
3. Upload one photo and run that recipe's prompt inside mosAIc. No copying text or switching AI tools.
4. See the result together with the recipe it used and who shared the prompt.

The core journey is **Discover → Recipe → Create → Result**, with the creator visible at every step.

## Principles

- AI should make creativity easier to access.
- Creators stay visible. Every recipe and every result links to the original post, and to the creator's Instagram once it has been verified.
- Unverified is not the same as allowed. A missing creator, IG link, preview or permission stays visibly "pending" (`來源待確認`). It is never filled in with a guess.
- Results tell the truth about how they were made:
  - `live`: generated just now from the visitor's photo.
  - `cached`: a prepared example made earlier from the team's test photo, labelled as such.
  - `mock`: a placeholder. Nothing was generated.
- A creator's attribution describes where the prompt came from. It does not mean the creator made the visitor's result.

## Recipe data

Each recipe in `apps/backend/data/recipes.json` has:

| Field                                | Meaning                                                                            |
| ------------------------------------ | ---------------------------------------------------------------------------------- |
| `id`                                 | Stable ID shared by every screen (`seed-01`, ...)                                  |
| `title`, `summary`                   | Working name and a one-line description of the effect                              |
| `sourcePostUrl`                      | The original social post. Always shown.                                            |
| `creatorName`, `creatorInstagramUrl` | `null` until checked against the original post                                     |
| `previewImageUrl`                    | Creator's preview, `null` until cleared for display                                |
| `inputNote`                          | What to upload (e.g. one photo, dogs only)                                         |
| `aspectRatio`                        | Output ratio the prompt asks for, sent to the image model                          |
| `prompt`                             | The full prompt, exactly as shared, never rewritten                                |
| `promptVisibility`                   | `public` shows the prompt on the recipe page; anything else keeps it on the server |
| `tryReady`                           | `true` only once the source and the basis for running the prompt have been checked |

The prompt is always looked up on the server by `recipeId`. The browser never sends prompt text, so the API key cannot be used to run arbitrary prompts.

## Current recipes

| ID        | Recipe                                                                                                                         | Input         |
| --------- | ------------------------------------------------------------------------------------------------------------------------------ | ------------- |
| `seed-01` | Photo + Geometric Editorial Poster: top half keeps the photo, bottom half becomes a geometric illustration; 3:4; no text       | One photo     |
| `seed-02` | Photo + Layered Paper-Cut Poster: top half keeps the photo, bottom half becomes layered paper-cut art with editorial type; 3:4 | One photo     |
| `seed-03` | Colored-Pencil Pet Portrait: a small colored-pencil head portrait on white; 4:5                                                | One dog photo |

The three prompts come from public Threads posts. Their creators, Instagram accounts and preview images have not been verified yet, so all three show `來源待確認` and are not yet open for Try.

## Out of scope for now

Accounts, payments, comments, a social graph, full creator profiles, recommendations, remix trees, and moderation infrastructure.
