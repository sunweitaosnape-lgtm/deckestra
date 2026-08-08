# Video Motion Plan

`video_motion_plan.py` converts a separately reviewed legacy or external
SVG-to-PPTX conversion trace into a renderer-neutral motion plan. It is a
compatibility handoff for an SVG-native or post-production video renderer.

**v0.1.0 boundary**: the public source release does not author object-animation
rows, so this compatibility tool does not activate object motion in a generated
deck. It may consume a separately obtained legacy/external resolved trace, but
that path is outside the v0.1.0 validated release claim. Page-transition and
Morph export do not require this planner.

The planner exists to prevent a video path from reducing animation to delay
values. The conversion trace is authoritative because it already contains the
resolved object target, effect, direction tuple, order, duration, offset, slide
advance, and native object bounds after sidecar inheritance and narration
synchronization.

---

## 1. Supply a Legacy or External Resolved Source Trace

The v0.1.0 public export path cannot generate an object-motion source trace.
If a separately obtained legacy or external resolved trace has been reviewed
and is permitted for the downstream video workflow, build the motion plan with:

```bash
python3 skills/build-editable-decks/scripts/video_motion_plan.py \
  <project_path>/validation/video_motion_source.trace.json \
  -o <project_path>/validation/video_motion_plan.json \
  --style adaptive \
  --force
```

`restrained` and `dynamic` are explicit intensity alternatives. `adaptive` is
the default and adjusts enhancement strength from page role, animated-object
count, and object area.

---

## 2. Authority and Locks

The downstream renderer must preserve:

- object identity and SVG group id;
- object order;
- source effect;
- semantic direction;
- resolved start time and slide timing anchor.

The video layer may optimize only the declared `optimizer_scope` parameters:
easing, travel distance, opacity, scale, mask feather, blur, motion blur, and
overshoot. These additions can make motion feel more cinematic without
rewriting the presentation's choreography.

Do not derive a video plan directly from a raw sidecar. Use only an already
resolved, separately reviewed trace, and do not treat that compatibility input
as proof that v0.1.0 authored its object effects.

---

## 3. Effect Mapping

Each object keeps `source_effect` and receives a compatible video family:

| Source effect | Video family |
|---|---|
| `entrance_appear` | `hard_reveal` |
| `entrance_fade` | `soft_fade` |
| `entrance_dissolve` | `grain_dissolve` |
| `entrance_fly`, `entrance_ascend` | `directional_slide` |
| `entrance_wipe`, `entrance_peek` | `soft_mask_reveal` |
| `entrance_zoom`, `entrance_expand`, `entrance_stretch` | `focus_scale` |
| `entrance_split` | `split_mask` |
| `entrance_box`, `entrance_circle`, `entrance_diamond`, `entrance_plus` | `shape_mask` |
| `entrance_blinds`, `entrance_checkerboard`, `entrance_random_bars`, `entrance_strips`, `entrance_wedge`, `entrance_wheel` | `pattern_reveal` |
| `entrance_swivel` | `soft_swivel` |

This mapping is an enhancement contract, not permission to substitute an
unrelated effect. A directional slide remains directional; a wipe remains a
mask reveal. The retired short effect names remain readable in older
conversion traces; compatible external traces should use canonical PowerPoint
keys.

---

## 4. Output Contract

The output schema is `deckestra.video-motion-plan.v1`. Each slide records:

- SVG source and canvas size;
- page role;
- slide duration and its source;
- resolved transition;
- ordered animated objects.

Each object records:

- `group_id`, native `shape_id`, and order;
- source effect and trigger;
- absolute `start_ms` and `duration_ms`;
- native `bounds_emu` and normalized area;
- renderer parameters under `video`.

The planner rejects click-triggered animation because a rendered video has no
interactive click event. Supply a reviewed legacy/external trace whose timing
is already click-free; this release cannot rewrite the object timing.

---

## 5. Current Boundary

This compatibility script owns only the semantic handoff and deterministic
enhancement policy for an accepted external trace. It does not encode video by
itself. A renderer that consumes the plan must report
unsupported families instead of silently falling back to delay-only fades.
