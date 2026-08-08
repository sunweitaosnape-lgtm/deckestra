# Deterministic layout contract

Use this path for flat decks whose pages can be expressed by the supported
typed layouts. The model chooses content, hierarchy, page roles, and theme; the
engine owns coordinates, wrapping, safe areas, spacing, and bounded fit repair.

## Privacy boundary

- Write `deck_ir.json`, `svg_output/`, and `validation/layout_trace.json` only
  inside the active external project workspace.
- Never copy the IR, rendered pages, or trace into the Skill, repository,
  examples, tests, documentation, release evidence, or another project.
- The trace records hashes, counts, boxes, line counts, and issue codes. It does
  not record user text, source passages, source locators, images, or secrets.
- The engine is local-only and performs no network, provider, or global-cache
  lookup.

## Typed IR

The complete machine grammar is
[`deck_ir.schema.json`](./deck_ir.schema.json). Runtime validation is stricter
than JSON Schema where cross-field or roster consistency is required.

| Area | Contract |
| --- | --- |
| Schema | Root `schema` is exactly `deckestra-ir/v1` |
| Roster | 1–100 pages with sequential `P01`… ids and safe unique slugs |
| Sources | Optional declared IDs; every page/item source reference must resolve |
| Theme | Six `#RRGGBB` roles and explicit title/body font families |
| Layouts | `cover`, `section`, `statement`, `title-body`, `two-column`, `cards`, `metrics`, `process`, `table`, `bar-chart`, `quote`, `closing` |
| Output | Complete standalone SVG pages made from native text and SVG primitives |

Do not put absolute coordinates in the IR. Do not flatten a table, chart, text
block, or metric into a screenshot. Keep facts and exact wording in typed
fields; use `source_ids` for element-level provenance.

## Execution

```bash
python3 ${SKILL_DIR}/scripts/deterministic_layout.py <project_path> --input deck_ir.json --repair-budget 2
```

The project must be outside the Deckestra repository. The command writes a
successful `validation/layout_trace.json` only after every page fits. A failed
run writes `validation/layout_trace.failed.json` and no SVG output.

The three permitted passes are fixed:

1. base typography and spacing;
2. 0.92 typography scale and 0.88 gap scale;
3. 0.84 typography scale and 0.76 gap scale.

After the third pass, any overflow is a hard failure. Never truncate, clip,
hide, ellipsize, shrink below the engine floor, or silently add/remove pages.

## Output ownership

The engine may replace an existing roster only when every current SVG still
matches the prior successful layout trace. A changed roster additionally
requires `--replace-managed`; the command deletes only stale files bound by
that prior trace. Any unbound or modified file blocks replacement.

After a pass, treat `deck_ir.json` as the owning source. Do not hand-edit an
engine-owned SVG. Correct the IR and rerun. A page that needs a visual outside
the supported grammar must switch the whole run to the documented manual lane;
the frozen release-evaluation profile treats that need as a failed case.

Before the SVG quality gate and again before export, verify that neither the IR
nor any generated page changed:

```bash
python3 ${SKILL_DIR}/scripts/layout_trace_gate.py <project_path> --input deck_ir.json --require-budget 2
```
