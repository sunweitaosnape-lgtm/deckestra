# Third-party notices

Parts of this Skill's presentation conversion and workflow implementation are
included or adapted from `hugohe3/ppt-master` at commit
`bbb323f0ebd6a6a230dd6063209326b53bfd2e1d` under the MIT License.

Copyright (c) 2025-2026 Hugo He

The complete upstream notice is preserved in
`third_party/ppt-master/MIT.txt`. This Skill is independently developed and
maintained and is not an official, certified, sponsored, or endorsed upstream
release.

## DrawingML preset geometry data

`scripts/pptx_shapes/data/presetShapeDefinitions.xml` is derived from Apache
POI 5.4.1 and is distributed under the Apache License 2.0.

`scripts/pptx_shapes/data/shape_type_values.txt` is derived from Open XML SDK
schema metadata and is distributed under the MIT License.

The pinned revisions, source and vendored hashes, license texts, and Apache
NOTICE are preserved in `scripts/pptx_shapes/data/`.

No third-party icon package, sample deck, screenshot, photograph, video, audio,
or font file is included in this Skill.

The public Skill excludes the former `scripts/pptx_animation_presets.json`
PowerPoint behavior-tree capture because its generation and redistribution
provenance was insufficiently documented. Consequently v0.1.0 does not author
per-object animations. Page transitions and registry-independent structural
checks for existing timing XML remain available.

Python packages listed in the requirements files are installed separately and
remain under their own licenses. The full optional `requirements.txt` includes
PyMuPDF and EbookLib under GNU AGPL 3.0 terms or, for PyMuPDF, an available
commercial license; edge-tts is primarily GNU LGPL 3.0. CairoSVG and svglib,
when independently installed and detected, are GNU LGPL 3.0. The v0.1.0
automated release claim covers only the fixed core and maintainer environment,
not the full optional runtime. Review the repository-level third-party notice
before installing or redistributing optional features.
