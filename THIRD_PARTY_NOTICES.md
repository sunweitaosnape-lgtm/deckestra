# Third-party notices

Parts of the presentation conversion and workflow implementation are included
or adapted from `hugohe3/ppt-master` at commit
`bbb323f0ebd6a6a230dd6063209326b53bfd2e1d`, distributed under the MIT License.

Copyright (c) 2025-2026 Hugo He

The complete upstream MIT notice is preserved in
`third_party/ppt-master/MIT.txt`. This project is independently developed and
maintained. It is not an official, certified, sponsored, or endorsed release of
the upstream project.

## DrawingML preset geometry data

`skills/build-editable-decks/scripts/pptx_shapes/data/presetShapeDefinitions.xml`
is derived from Apache POI 5.4.1 and is distributed under the Apache License
2.0. The source revision, normalization note, hashes, license text, and Apache
NOTICE are preserved beside the vendored file.

`skills/build-editable-decks/scripts/pptx_shapes/data/shape_type_values.txt` is
derived from Open XML SDK schema metadata and is distributed under the MIT
License. Its pinned revision, source and vendored hashes, and license text are
preserved beside the file.

No third-party icon package, sample deck, screenshot, photograph, video, audio,
or font file is included in this repository.

The public source release also excludes the former
`skills/build-editable-decks/scripts/pptx_animation_presets.json` capture. Its
PowerPoint-generated behavior-tree rows did not have a sufficiently documented
capture method and redistribution basis for this release. Deckestra v0.1.0
therefore does not author per-object animations; it retains page transitions
and registry-independent structural checks for existing timing XML.

`release/upstream-map.lock.json` records the same-relative upstream path,
pinned Git blob SHA-1, and identical/modified relation for every retained Skill
file classified as adapted from `hugohe3/ppt-master`. For v0.1.0 it covers 582
files: 377 byte-identical and 205 modified. The whole-tree provenance lock
separately pins the current SHA-256 of every public file.

## Separately installed Python dependencies

Python packages named in the requirements files are not copied or vendored in
this repository. They are installed separately from their publishers and remain
under their own licenses. The Deckestra MIT License does not replace those
licenses.

The fixed v0.1.0 automated release environment uses
`requirements-core.txt` and `requirements-maintainer.txt`. The broader
`requirements.txt` is an unvalidated convenience list for optional features and
includes components with copyleft or dual-license terms:

| Package or optional backend | Upstream license |
|---|---|
| PyMuPDF | GNU AGPL 3.0 or Artifex commercial license |
| EbookLib | GNU AGPL 3.0 |
| edge-tts | GNU LGPL 3.0 for most files; one SRT helper is MIT |
| CairoSVG | GNU LGPL 3.0; detected only when separately installed |
| svglib | GNU LGPL 3.0; detected only when separately installed |
| Playwright for Python | Apache License 2.0; detected only when separately installed |
| stable-ts | MIT; detected only when separately installed |

Installing, modifying, or distributing an optional runtime may create
obligations beyond Deckestra's MIT terms. Review the license shipped by the
exact package version before redistribution. No optional dependency license is
relicensed by this repository.
