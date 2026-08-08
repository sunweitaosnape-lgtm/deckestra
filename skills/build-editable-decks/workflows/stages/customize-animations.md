---
description: Optional post-processing stage for page-transition, auto-advance, and deterministic Morph overrides.
---

# Customize Transitions Stage

Use this stage only for generated SVG projects that need page-specific
transitions, automatic advance, or deterministic Morph object pairing.

## Public release boundary

Deckestra v0.1.0 does not author in-slide object animations. The required
captured behavior-tree registry was excluded because its capture and
redistribution provenance was insufficiently documented. Do not write
`animation`, `groups`, object effects, triggers, timing rows, or animation
sounds to `animations.json`. Export must retain `-a none`.

If the user requests a reveal, emphasis, motion path, same-page exit, or click
trigger, state that this release cannot author it. Offer a page-to-page Morph
sequence only when separate static endpoint slides communicate the same intent.

## When to run

| Signal | Action |
|---|---|
| One deck-wide page transition or advance interval | Apply exporter flags; this stage is optional |
| Page-specific transition settings | Run this stage |
| Same semantic object continues across adjacent slides and identity matters | Run this stage and declare Morph pairs |
| Existing transition-only `animations.json` | Run this stage to validate it |
| Only in-slide object animation is requested | Do not run; explain the release boundary |

## 1. Read the final page roster

Run only after the final SVG quality gate. Inspect the ordered final
`svg_output/` roster and the direct-root group IDs on every page involved in a
Morph pair. Do not use a stale sidecar or an earlier SVG directory.

For each requested transition, name its communication job: neutral continuity,
directional progress, a section boundary, or continuous object/state change.
Keep `fade` when no stronger relationship exists.

## 2. Write sparse overrides

Write only pages that differ from the deck-wide exporter settings. A valid
v0.1.0 sidecar can contain `transition` and `morph` fields:

```json
{
  "version": 1,
  "slides": {
    "02_detail": {
      "transition": {
        "effect": "morph",
        "effect_options": { "morph_by": "object" },
        "duration": 0.8
      },
      "morph": {
        "from": "01_overview",
        "pairs": {
          "hero-image": {
            "from": "hero-overview",
            "to": "hero-detail"
          }
        }
      }
    }
  }
}
```

Rules:

- Slide keys are real final SVG stems.
- `morph.from` is the immediately preceding stem in export order.
- Pair endpoints are unique direct-root group IDs on the two adjacent pages.
- Pair keys omit the `!!` prefix; export adds and verifies it.
- Both endpoints resolve to compatible PowerPoint object kinds.
- A declared Morph pair never falls back to heuristic matching.
- Do not add animation fields to SVG.

Use [`animations.md`](../../references/animations.md) for the exact transition
selection and Morph contract.

## 3. Validate and export

```bash
python3 skills/build-editable-decks/scripts/animation_config.py \
  validate <project_path>
python3 skills/build-editable-decks/scripts/svg_to_pptx.py \
  <project_path> -a none
```

For one deck-wide transition, flags may be clearer than a sidecar:

```bash
python3 skills/build-editable-decks/scripts/svg_to_pptx.py \
  <project_path> -t push --transition-duration 0.6 -a none
```

Export reopens the package and validates the requested transition and explicit
Morph identities. Unknown effects, unsupported options, stale targets, or
object-animation rows fail closed.

## Completion handoff

Report:

- transition effect, duration, and advance behavior;
- affected page stems;
- every explicit Morph key and endpoint pair;
- sidecar validation result; and
- confirmation that object-animation authoring remained disabled.

Then return to the active Generate export authority. This stage never publishes
or uploads an artifact by itself.
