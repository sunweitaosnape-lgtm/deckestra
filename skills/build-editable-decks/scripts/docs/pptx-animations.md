# PPTX Animation Boundary

## Public v0.1.0 capability

The public source release does not author in-slide object animations. The
captured PowerPoint behavior-tree registry formerly used by the writer was
removed because its generation method, exact Office build, and redistribution
basis were not sufficiently documented. The CLI and sidecar validators accept
only object effect `none` and fail closed for all named effects or automatic
selection modes.

Page transitions and deterministic Morph object pairing are separate and remain
supported. See [`../../references/animations.md`](../../references/animations.md)
and [`pptx-transitions.md`](./pptx-transitions.md).

## Code ownership

| Concern | Owner |
|---|---|
| Page-transition generation and validation | `pptx_transitions.py` |
| Shared timing-tree parsing and structural validation | `pptx_animations.py` |
| Sidecar schema and target validation | `svg_to_pptx/animation_config.py` |
| Generated package integration | `svg_to_pptx/pptx_package/builder.py` |
| Direct-PPTX structural checks | `pptx_delivery_check.py` and route-specific callers |

`pptx_animations.py` retains registry-independent readers, fingerprints, timing
ID checks, target-reference checks, and preservation helpers. That code does
not imply permission to create new Animation Pane rows without a reviewed
preset source.

## Fail-closed contract

- `NATIVE_ANIMATIONS`, `ANIMATIONS`, and `ANIMATION_MODES` are empty.
- `OBJECT_ANIMATION_AUTHORING_AVAILABLE` is `False`.
- `normalize_animation_effect(None)` and `normalize_animation_effect("none")`
  resolve to no object effect.
- Every other requested object effect raises `ValueError`.
- `svg_to_pptx.py -a none` remains valid; no captured registry file is read at
  import time.
- `animations.json` may carry transition and Morph fields, but object
  `animation`, `groups`, effect options, triggers, and sounds are outside the
  public contract.

Do not add a replacement registry by copying behavior XML from PowerPoint or
another binary without a documented generator, exact source/build identity,
license analysis, hashes, notices, and explicit release approval.

## Existing PPTX boundary

Direct-PPTX routes do not author or edit object effects. They may preserve
existing timing XML while validating registry-independent structure:

- timing nodes remain under one valid slide timing root;
- time-node IDs are well formed and non-duplicated;
- shape targets exist in the same slide;
- source fingerprints remain unchanged when the route promises preservation.

Generated-output validation must not treat an unknown existing effect as a
supported authoring preset. Preservation and authoring are different claims.

## Compatibility scope

PowerPoint OOXML is the structural compatibility target. Slide Zoom, Summary
Zoom, paragraph builds, Chart/SmartArt build sequences, media play/pause/stop,
and new per-object animation rows are not authored by v0.1.0.

Microsoft implementation references used by the transition and structural
validators:

- [MsoAnimEffect enumeration](https://learn.microsoft.com/en-us/office/vba/api/powerpoint.msoanimeffect)
- [Sequence.AddEffect](https://learn.microsoft.com/en-us/office/vba/api/powerpoint.sequence.addeffect)
- [Effect.Exit](https://learn.microsoft.com/en-us/office/vba/api/powerpoint.effect.exit)
- [Animation-filter implementation notes](https://learn.microsoft.com/en-us/openspecs/office_standards/ms-oe376/a96dab70-2e72-4319-928d-0eb4b275ce58)
