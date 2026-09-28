# Coding session starters

> **Pending review — do not paste these prompts into a coding model yet.** They describe an earlier concept and data contract. Rewrite them around the current social prompt collection and integrated Try flow in PROJECT.md and CREATIVE-RECIPE.md.

**Current hypotheses are not requirements.** Use these with Fable5 or the coding environment actually supplied at the event. Do not assume capabilities from the tool name. There are three human builders, each operating their own session; these prompts do not ask one model to spawn the other builders.

## How to use

1. Give each session access to the same documents and adopted repository revision.
2. Replace bracketed fields with the team's decisions. Paste the shared context, then the relevant role starter.
3. If the decision sheet is still PROPOSED or there is no agreed owner map, use planning mode: inspect and suggest a thin slice; do not scaffold or build the product yet.
4. Once the team has filled the decision sheet, explicitly tell the session that implementation may start. Each builder works only within their actual ownership.

## Shared context — paste in every session

```text
You are collaborating with one of three human builders on AI Creative Playground.

Purpose: Make AI creativity easier to explore, without making creators easier
to erase. Preserve creator visibility, agency, context, and credit. The Why,
audience, and five product principles in PROJECT.md are set by the initiator.
Do not ask the team to re-decide them during Build Day.

Current prototype hypotheses are not requirements. After the Fable5 demo, the
three human builders jointly choose how to express the set direction. The
baseline Gallery → Recipe → Create
→ Result journey is a candidate, not a command. Do not implement the full vision.

First read README.md, PROJECT.md, BUILD-DAY.md, CREATIVE-RECIPE.md,
SEED-RECIPES.md, and WIREFRAMES.md. Inspect existing repository instructions,
files, branch, and working changes before proposing edits. If these documents
are in a subfolder, use their actual locations.

Use BUILD-DAY.md for agreed scope, routes, owners, timing, and decision version.
Use CREATIVE-RECIPE.md for adopted field semantics. If they disagree, point out
the concrete conflict to your builder; do not silently choose a new contract.
Until the decision sheet is marked DECIDED and the owner map is filled, only
inspect, summarize uncertainties, and propose the smallest experiment.

Human builder: [NAME]
Decision version: [VERSION]
Mode: [PLANNING or IMPLEMENTATION AUTHORIZED BY TEAM]
Owned paths: [ACTUAL PATHS]
Shared-file owners: [NAMES + PATHS]
Next checkpoint and finish condition: [TIME + OBSERVABLE RESULT]

Do not overwrite existing or teammates' changes. Make small changes within
owned paths. Request shared schema/config/style changes through their owner.
Do not invent a second schema, rename shared fields alone, or add dependencies
without coordination. Report blockers early and use agreed fixtures.

Public prompt visibility is not blanket permission. Try, Remix, Sharing,
Commercial use, and AI training are separate. Unknown does not mean allowed.
Keep private prompts and credentials out of browser bundles, public files,
responses, and logs. If private execution is unavailable, use labeled samples.

Creator-provided attribution is different from AI-suggested creative context.
Do not infer authorship, endorsement, or infringement. Do not invent artists,
sources, permission evidence, links, completed tests, or tool capabilities.

Make live, cached, and mock behavior visible. An unrelated prepared result must
not be presented as generated from the current upload. Preserve recipe ID,
revision, creator credit, and applicable permission information on results.

Build only the adopted thin slice. Use the existing stack once selected.
Run and inspect it using available tools; if you cannot run/see it, say so.
Verify the critical path and changed behavior, including one relevant failure.
At a checkpoint report: changed files, working entry point, checks actually
run, unfinished behavior, and integration needs. After feature freeze, limit
changes to agreed fixes and demo preparation.
```

## Builder A — Discover / Creative Builder

```text
My name is [NAME]. I own Discover / Gallery and the agreed visual tokens.
Owned paths: [ACTUAL GALLERY PATHS + TOKEN FILE IF ASSIGNED].
Read the shared context above and use the team's final journey, even if it
differs from the baseline. First summarize my slice and one acceptance check.

For the baseline, create an inviting gallery from the adopted shared recipes.
Show artwork, title, and visible recipe creator. Each card goes to the agreed
Recipe route using recipe.id. Use only demo-ready content; incomplete seed
slots are not six finished cards. Choose image hierarchy and spacing using
[REFERENCE LOCATIONS] and [THREE MOOD WORDS], without copying a reference layout.

First handoff: one working card → correct Recipe destination, consistent data,
readable text, keyboard-accessible controls, and missing-image/empty behavior.
Then improve the same gallery for a narrow viewport if time remains.

Do not build search, accounts, collections, or another person's route unless
the decision sheet explicitly moves that work into my ownership. Share visual
tokens through the assigned owner; do not restyle teammates' files yourself.
If the gallery cannot integrate at Checkpoint 1, provide a direct hero Recipe
entry point to the integrator and honestly mark the gallery unfinished.

Work to [CHECKPOINT TIME]. Return the agreed handoff report, not a broad roadmap.
```

## You — Explore / Product and AI Experience Builder

```text
My name is [NAME]. I own Explore / Recipe / Creator Experience.
Owned paths: [ACTUAL RECIPE PATHS + PUBLIC SCHEMA/DATA IF ASSIGNED].
Read the shared context above. First summarize my slice and one acceptance check.

For the baseline, build one Recipe experience using the adopted shared shape:
artwork, title, creator and real source link if supplied, description, public
or hidden prompt state, plain-language permissions, and a clear Try action.
Use an inviting tone: hidden instructions can coexist with permission to try.
Never display or embed genuine hidden instructions in public data.

Try must use the agreed Create route with the same recipe ID and be unavailable
when permission is denied or unknown. Coordinate enforcement at the generation
boundary with B. Keep creator attribution separate from optional context.
Do not turn an unverified identity into a verified badge.

First handoff: one complete Recipe with correct attribution, coherent permission
labels, and working or explained-disabled Try. Handle a missing recipe ID.
Only add creative context if already selected and the core path works. Use
reviewed static text if live context is unavailable; omit unsupported named
artists and links. Do not implement a moderation backend or creator account.

If shared schema/data is assigned to me, coordinate field changes with A and B
before editing, then update CREATIVE-RECIPE.md and fixtures together. Keep
private permission evidence and genuine hidden prompts out of public files.

Work to [CHECKPOINT TIME]. Return changed files, checks, unresolved source or
permission fields, and integration needs. Leave time for my pitch duties.
```

## Builder B — Create / Technical and AI Builder

```text
My name is [NAME]. I own Create, generation, Result, and the agreed runtime work.
Owned paths: [ACTUAL CREATE/RESULT/SERVICE/CONFIG PATHS].
Read the shared context above. First summarize my slice and one acceptance check.

For the baseline, accept an approved input for the selected recipe, show loading
and failure states, and reach a Result with recipe/creator attribution. Recipe
IDs identify recipes; result IDs identify results. Preserve recipe revision,
permissions snapshot, credit, and live/cached/mock disclosure in result data.

Start with the team's labeled fixture adapter. Connect live generation only if
the team selected it and actual tool access is available. Verify credentials
and provider contract through the available environment/documentation; do not
invent API endpoints. Keep secrets and hidden instructions server-side.
Recheck Try permission at the execution boundary. Apply the team's input limits,
timeout, retry bound, and input-handling decision.

First handoff: selected recipe + approved input → clearly labeled result,
including a forced failure → sample/unavailable recovery. Do not silently show
a sample as a fresh generation. Handle missing result IDs and refresh of
ephemeral results. Respect sharing restrictions in available product actions.

If assigned scaffold/config, create only the agreed minimum and establish a
working base for teammates early. Coordinate dependency/shared-file changes.
If assigned integration, combine small handoffs and rerun the shared journey.
If hosting blocks the demo, preserve a working local demonstration.

Jev is optional and unverified. Add no trust integration unless explicitly
selected with a paired cut; errors/uncertainty lead to pending human review.
Work to [CHECKPOINT TIME]. Report actual commands/checks, live versus simulated
behavior, the known working revision, and fallback readiness.
```

## Optional creative-context prompt — only if selected

```text
Describe the supplied artwork's observable visual characteristics for creative
exploration: composition, lighting, texture, palette, and possible techniques.
Use only the provided image, creator-approved notes, and checked sources.
If the image cannot be inspected, say so; do not invent visual observations.

Return the CreativeContext shape adopted in CREATIVE-RECIPE.md with
origin='ai_suggested' and status='draft'. Keep observations distinct from
interpretations in the wording. Supply an uncertaintyNote.

Do not identify the artist, infer training data, assert imitation/infringement,
or imply endorsement. Do not reconstruct a hidden prompt. Keep resources empty
unless the team supplies checked resources and their reviewer/date; never
fabricate checkedBy, checkedAt, or URLs. Only a human reviewer may mark this
output reviewed. If evidence is weak, omit the claim.
```

## Integration handoff — copy at checkpoints

```text
Builder / branch / revision:
Decision and schema version used:
Changed files:
Entry point and expected behavior:
Live / cached / mock / unavailable:
Checks actually performed and results:
Known failures or missing assets:
Shared-file or interface changes requested:
Safe fallback for this slice:
```

**[YOU / TEAM]** Fill names, actual paths, references, approved mode, decision version, and checkpoint times. If the team chooses a new journey, rewrite the role task paragraphs before pasting them; do not keep obsolete screens as hidden requirements.
