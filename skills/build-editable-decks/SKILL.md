---
name: build-editable-decks
description: Create, redesign, fill, validate, and enhance polished PowerPoint presentations with natively editable text, shapes, tables, charts, notes, transitions, and template-aware layouts. Use when Codex needs to build a PPT or PPTX from documents, PDFs, papers, data, an existing presentation, a reusable template, or a topic, and when whole-deck quality, source fidelity, privacy, and reproducible validation matter.
---

# Build Editable Decks

Build one coherent presentation artifact and prove that the delivered file is
current, complete, editable, visually usable, and faithful to its sources.

## Mandatory load order

1. Run `python3 scripts/attribution_guard.py` from this Skill directory.
2. Read [`workflows/routing.md`](workflows/routing.md).
3. Select exactly one top-level route and one active profile.
4. Read only the selected runtime authority and its explicitly triggered
   references.
5. Follow every blocking gate owned by that route.

## Privacy discipline

- Keep the Skill directory read-only during a user run.
- Create every project in a user-approved external directory or a private
  temporary directory. Never create runtime projects inside this Skill or its
  source repository.
- Never copy user inputs, extracted text, images, generated slides, renderings,
  audio, logs, or evaluation artifacts into this package.
- Keep source conversion, OCR, image analysis, rendering, and export local by
  default. Send source content or derived assets to a remote provider only when
  the user explicitly requests the provider-dependent capability.
- Do not reuse one user's source, image, template, wording, or output in another
  run, example, test, benchmark, or documentation page.
- Record hashes, source IDs, status, and bounded diagnostics. Do not record raw
  source passages, image bytes, secrets, private reasoning, or credential-bearing
  URLs in operational logs.
- Use synthetic public fixtures. Treat any real user artifact found inside the
  package as a blocking integrity failure.
- Remove private temporary workspaces after delivery when they are not needed
  for an active revision. Preserve a project only when the user requests it.

## Route selection

| Route | Use for | Runtime authority |
|---|---|---|
| Generate PPTX | New deck, visual regeneration, source-to-deck, topic-to-deck | `workflows/generate-pptx.md` or the explicit Quick profile |
| Create Template | Reusable Brand, Style, Layout, or Deck workspace | `workflows/create-template.md` |
| Fill Native PPTX | Replace content in existing native slide shells | `workflows/template-fill-pptx.md` |
| Enhance Native PPTX | Preserve visible slides while adding notes, timings, transitions, or narration | `workflows/native-enhance-pptx.md` |

Use `workflows/profiles/beautify-pptx.md` when wording, page count, and page
order must remain 1:1. Use `workflows/profiles/quick-generate.md` only when the
user explicitly requests a quick or no-confirmation run.

## Whole-deck contract

Treat a deck as passed only when all applicable conditions pass:

- Every required source and page is represented.
- Assertions, numbers, tables, charts, images, citations, and notes trace to an
  identified source or an explicit assumption.
- No invented fact, unsupported trend, or silent omission remains.
- Every page has one clear communication job and a visible hierarchy.
- Text does not overflow, clip, collide, or become unreadable after rendering.
- Color, spacing, typography, alignment, and template behavior remain coherent.
- Text, ordinary shapes, tables, and supported charts stay natively editable.
- The PPTX package, relationships, notes, page transitions, preserved timing
  XML, and embedded resources are structurally valid.
- The final quality report binds the exact sources, page roster, SVGs,
  dependencies, renderings, PPTX, and postflight result by hash.

Do not average away a failed page. One blocking failure means the whole deck
fails until repaired or explicitly delivered as incomplete.

## Execution discipline

1. Read all supplied material before planning.
2. State or resolve the audience, objective, core message, page count, canvas,
   editability needs, language, and template constraints.
3. Build a source inventory and page roster before page authoring.
4. Use `deckestra-ir/v1` and `scripts/deterministic_layout.py` for supported
   flat layouts. Use manual SVG coordinates only for a documented unsupported
   visual or template contract; the frozen release profile permits no fallback.
5. Prefer native text, shapes, tables, charts, and Office geometry. Use raster
   images only when the content genuinely requires them.
6. Prepare every referenced resource before authoring the page that uses it.
7. Run structural checks, render checks, content checks, and editability checks.
8. Repair only the owning source or component. Deterministic layout gets at
   most two repair attempts, never truncates content, and retains a
   machine-readable trace without user text.
9. Export one final PPTX and bind it to the current evidence. Any later file
   change invalidates the prior pass.

## Communication

- Match the user's language and the source language unless explicitly changed.
- Lead with the outcome and material blockers.
- Ask only for a decision that changes the artifact materially or resolves a
  hard prerequisite.
- Do not claim a quality rate from a single successful deck or a development
  set. Use only the frozen release evaluation policy for public quality claims.
