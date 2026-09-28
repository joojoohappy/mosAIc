# MOSAIC — Build Day Team Structure

## Project Goal

MOSAIC is an AI Creative Playground that makes AI creativity easier to discover and try, while keeping original creators visible and giving them agency over how their creative work is used.

Core idea:

**Discover → Explore → Try → Create**

Build Day is a prototype, not a complete product.

Our priority is to create **one complete, demoable user journey** rather than many unfinished features.

---

# Team Structure

We are a two-person team.

Instead of splitting work equally by pages, we divide ownership by responsibility:

## Person 1 — Product / Creative / Frontend Experience

Owns everything the user **sees, understands, and interacts with**.

Primary responsibilities:

### 1. Product Direction

Maintain the core principles of MOSAIC:

- AI should make creativity easier to access.
- Creators should remain visible.
- Creator-provided attribution and AI-inferred context are different things.
- Creators should have agency over how their recipes are used.
- The prototype should prioritize experience over feature quantity.

Features and implementation are flexible.

The product principles are not.

---

### 2. Gallery / Discover Experience

Build the entry point where users discover Creative Recipes.

Each recipe may contain:

- Example artwork
- Recipe title
- Creator / source
- Creative category
- Short description

Primary goal:

**Make users want to explore a creation.**

---

### 3. Recipe / Explore Experience

Own the Creative Recipe detail experience.

Possible information:

- Artwork
- Creator identity
- Creator profile / source
- Description
- Prompt visibility: Public / Hidden
- Creative permissions
- Attribution requirements
- Creative Context
- Related artists / movements / techniques
- “Try this Recipe” CTA

This is the main page expressing MOSAIC's philosophy.

---

### 4. Create — Frontend Interaction

Own the frontend portion of creation:

- Image upload UI
- Selected Creative Recipe
- Generate button
- Loading state
- Error state

The backend implementation is owned by Person 2.

Frontend should communicate through an agreed API/interface.

---

### 5. Result Experience

Display:

- Generated artwork
- Recipe used
- Original creator
- Attribution

Optional features such as sharing/remixing should only be added if time remains.

---

### 6. Creative Direction

Use Fable to build and visually inspect the experience.

Iterate based on questions such as:

- Does this feel like a creative community rather than an AI SaaS dashboard?
- Is the creator sufficiently visible?
- Does the user understand why attribution exists?
- Do permissions feel understandable rather than legalistic?
- Does the Gallery make someone want to explore?
- Is the primary action obvious?

---

### 7. Integration + Demo

During the final phase:

- Stop adding features.
- Integrate frontend with backend.
- Test the complete journey.
- Switch to mocks/cached results if external services fail.
- Prepare and deliver the 2-minute demo.

---

# Person 2 — Backend / AI / Systems

Owns everything that happens **after the frontend asks the system to perform an action**.

Primary responsibilities:

### 1. Generation Pipeline

Implement:

**Input image + Creative Recipe → AI generation → Generated result**

Expose this through a simple interface/API that the frontend can call.

---

### 2. API / Model Integration

Own:

- Model/API calls
- Prompt application
- Image handling
- Response parsing
- Credentials/environment variables
- Error handling

The frontend should not need to understand the internal implementation.

---

### 3. Backend Data Handling

Support the minimum data required for the prototype.

Avoid building unnecessary production infrastructure.

Use mock/static data where appropriate.

---

### 4. Reliability + Fallback

Generation must have a fallback.

If live generation fails:

**use a pre-generated/cached result.**

The demo must not depend on one external API request succeeding.

---

### 5. Deployment / Technical Integration

Own or support:

- Backend deployment
- API connectivity
- Environment configuration
- Integration debugging

Ensure the frontend can successfully call the generation service.

---

### 6. Optional AI / Trust Features

Only if the core generation flow is stable:

- Creative Context service
- Jev-based content/attribution classification
- Creator submission checks

These are P1/P2 features and must not endanger the core demo.

---

# Shared Contract

Before parallel development, both people agree on:

## Core Journey

Baseline:

**Gallery → Recipe → Create → Result**

This may be changed together after seeing the Build Day demo.

---

## Route Contract

Example:

```text
/
→ /recipe/:id
→ /create/:id
→ /result/:id
```

---

## CreativeRecipe Contract

Both frontend and backend should use the same conceptual data structure:

```text
CreativeRecipe

id
title
description
exampleImage

creator
  name
  profileUrl

prompt
  content
  visibility

permissions
  tryAllowed
  remixAllowed
  sharingAllowed
  commercialUse
  aiTraining
  attributionRequired

creativeContext
  aesthetics
  movements
  relatedArtists
  resources
```

The exact schema may change during Build Day, but both people must agree before changing shared fields.

---

# Build Strategy

## Mock First

Frontend must be buildable without backend completion.

Backend must be testable without frontend completion.

For example:

```text
Frontend
real UI → mock generation result

Backend
API → test request / mock frontend
```

Then connect them.

---

## Failure Independence

The prototype should remain demoable even when individual features fail.

If generation fails:

→ cached generated image.

If Creative Context fails:

→ mock context.

If Jev fails:

→ skip Trust feature / show Pending Review.

If Gallery fails:

→ open Recipe directly.

---

# Build Day Decision Rule

The current product structure is a **hypothesis, not a fixed PRD**.

After watching the Fable demo, both team members should discuss:

```text
KEEP
What from the current concept should remain?

CHANGE
What should work differently?

ADD
What ONE capability demonstrated today would improve the prototype?

CUT
What will we remove to make room for it?
```

Rule:

**ADD ONE → CUT ONE.**

Neither team member should simply execute the original plan if the demo reveals a better interaction.

---

# Priority

## P0 — Must Work

One complete journey:

**Discover → Explore → Try → Create → Result**

with creator attribution preserved.

## P1 — If Core Journey Is Stable

- Creative Context
- Artist / movement discovery
- Better permissions experience
- Live generation improvements

## P2 — Only If Unexpectedly Ahead

- Jev Trust Layer
- Creator submission
- Sharing
- Remix
- Moderation

Do not build:

- Authentication
- Payment
- Social graph
- Comments
- Full creator profiles
- Recommendation engine
- Production moderation infrastructure

---

# Success Condition

The prototype succeeds if someone can:

**discover an AI creation → understand who/where it came from → try it with their own content → receive a result → still see the original creator in the creative chain.**

Everything else is optional.
