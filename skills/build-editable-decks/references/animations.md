# Page Transitions and Morph

Execution contract for generated-PPTX page transitions, automatic slide
advance, and deterministic Morph object pairing.

## Release boundary

Deckestra v0.1.0 does not author in-slide per-object animations. The captured
PowerPoint behavior-tree registry previously required for that feature was
removed because its capture and redistribution provenance was insufficiently
documented. Export accepts only `-a none`; any sidecar that requests an object
effect fails validation.

This boundary does not remove:

- the 48 page-transition keys implemented from the documented OOXML contract;
- `none`, transition duration, or automatic slide advance;
- Morph, including explicit cross-slide object pairing; or
- registry-independent structural checks used when a direct-PPTX route
  preserves existing timing XML.

Do not run the transition stage in response to an in-slide reveal, emphasis,
motion-path, exit, or click-trigger request. Explain that object-animation
authoring is unavailable in this release and offer a page-to-page Morph
sequence when it communicates the same idea.

## Defaults

| Setting | Default | Meaning |
|---|---|---|
| Page transition | `fade`, 0.4 seconds | Calm continuity within a section |
| Object animation | `none` | Required public-release setting |
| Slide advance | Manual | Omit `--auto-advance` |

Use motion only when it expresses a real relationship between pages. Keep
`fade` or `none` when another effect adds no meaning; never vary transitions
for gallery coverage.

## Page-transition selection

| Page relationship | Candidate |
|---|---|
| Ordinary continuation | `fade` |
| Immediate change without continuity | `none` or `cut` |
| Directional steps or timeline | `push` or `wipe` |
| Same semantic object or scene changes state | `morph` |
| Deliberate section boundary | Selective `split`, `reveal`, or `shape` |
| Spatial travel is central to the story | Selective `pan`, `orbit`, or `fly_through` |

List the exact categorized identifiers and inspect effect-specific options:

```bash
python3 skills/build-editable-decks/scripts/pptx_animations.py --list
python3 skills/build-editable-decks/scripts/pptx_animations.py \
  --describe-transition push
```

Export examples:

```bash
# Directional transition
python3 skills/build-editable-decks/scripts/svg_to_pptx.py \
  <project> -t push --transition-duration 0.6

# No visual transition
python3 skills/build-editable-decks/scripts/svg_to_pptx.py <project> -t none

# Kiosk-style advance, with or without a visual transition
python3 skills/build-editable-decks/scripts/svg_to_pptx.py \
  <project> --auto-advance 5
python3 skills/build-editable-decks/scripts/svg_to_pptx.py \
  <project> -t none --auto-advance 5
```

Unknown effects, inapplicable options, and invalid or non-finite durations fail
closed. They are never silently replaced by `fade`. Recorded narration keeps
the resolved visual transition; `-t none` stays visually motion-free.

## Deterministic Morph pairing

Morph authors continuous action as two ordinary editable pages with different
static states. Prefer explicit pairing whenever identity matters. Put the
pairing on the destination slide in `animations.json`:

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

- `morph.from` is the immediately preceding SVG stem in export order.
- Each pair key is a stable identity. Supply it without `!!`; export writes
  `!!<key>` to both PowerPoint objects.
- `from` and `to` name unique direct-root `<g id>` elements on the source and
  destination slides.
- The destination must explicitly use `effect: morph`; `morph_by` is `object`.
- Reuse one key across a longer adjacent sequence. One object cannot have two
  keys and one key cannot name two objects on one slide.
- Both endpoints must resolve to compatible top-level PowerPoint object kinds.
  Geometry, crop, position, and size may differ.
- The exporter reopens the package and verifies adjacency, names, object kinds,
  and Morph-by-object. Missing or ambiguous targets fail; there is no heuristic
  fallback for a declared pair.

A fully off-canvas endpoint must be one direct-root group with valid
`data-pptx-bounds` and `data-pptx-morph-staging="true"`. The marker declares an
intentional invisible state; it never excuses clipped visible content.

## Sidecar boundary and validation

For v0.1.0, author `animations.json` with only transition and Morph overrides.
Legacy no-op object fields containing `effect: none` remain readable for
compatibility but create no Animation Pane rows. Any non-none object effect or
mode fails. Do not add animation metadata to SVG files.

Validate then export:

```bash
python3 skills/build-editable-decks/scripts/animation_config.py \
  validate <project>
python3 skills/build-editable-decks/scripts/svg_to_pptx.py <project> -a none
```

`--no-animations` disables both page motion and the sidecar. Use `-a none`
when page transitions or Morph must remain active.

## Limitations

- Slide Zoom and Summary Zoom are not authored.
- Object animation, Animation Pane rows, media commands, and click triggers are
  not authored in this release.
- PowerPoint OOXML is the compatibility target; other presentation apps may
  render transitions differently.
- Morph cannot turn a shape into a picture; incompatible kinds cross-fade.

## Implementation references

- `scripts/pptx_transitions.py`
- `scripts/pptx_animations.py`
- `scripts/animation_config.py`
- `scripts/svg_to_pptx.py`
- [`scripts/docs/pptx-transitions.md`](../scripts/docs/pptx-transitions.md)
