# Deckestra

Deckestra is an independently developed presentation Skill for creating and
editing PowerPoint decks. Its technical Skill name is
`build-editable-decks`.

The repository includes source traceability, structured story planning,
deterministic and template-aware layout, editable DrawingML export, rendering
checks, bounded repair, and release evidence.

## Included workflows

- Build new decks from text, PDFs, Word files, papers, spreadsheets, existing
  presentations, or a topic.
- Redesign a deck while preserving wording, page count, and order when requested.
- Fill an existing native PPTX without flattening supported objects.
- Create reusable brand, style, layout, and deck workspaces.
- Export editable text, ordinary shapes, tables, supported charts, notes, and
  page transitions.
- Keep source IDs and validation evidence connected to the exact exported file.

For text-first reports and technical briefs, the primary lane uses a typed deck
IR instead of model-written coordinates. It supports twelve editable page
families, performs at most two fit repairs, never truncates overflowing content,
and emits a content-free hash/geometry trace. Complex image compositions and
strict template reconstruction remain available through separately gated routes.

## Verified v0.1.0 scope

v0.1.0 is the initial public source release. Its automated release gate runs 46
unit and integration tests. The verified scope includes all twelve deterministic
layout families, zero-warning SVG quality checks for those families, repeatable
layout output, bounded overflow handling, native table and chart export smoke
tests, runtime privacy controls, complete reachable-history scanning, pinned
third-party data checks, and whole-tree provenance locking.

Object-animation authoring is intentionally excluded from v0.1.0 because its
former captured PowerPoint behavior-tree registry lacked sufficient
redistribution provenance. Page transitions, deterministic Morph pairing, and
structural preservation checks for existing PPTX timing XML remain available.

This release is not a quality-rate certification. A 99% whole-deck completion
statement remains a future target and requires the frozen
`zh-cn-tech-brief-15-v1` evaluation: 1,000 blind cases, at least 997 complete
passes, 15 pages per case, and two independent full-page reviews for every page.
See [`certification/`](certification/).

Optional document converters, remote image providers, narration backends, and
editor integrations are included but are not part of the v0.1.0 automated
release claim.

## Install as a local Skill

OpenAI's [official Skill documentation](https://learn.chatgpt.com/docs/build-skills)
defines a Skill as a directory containing `SKILL.md` plus optional scripts,
references, assets, and `agents/openai.yaml`. Python 3.12 is the validated
release environment.

Clone and validate the public source in a new virtual environment:

```bash
git clone https://github.com/sunweitaosnape-lgtm/deckestra.git
python3.12 -m venv deckestra-venv
source deckestra-venv/bin/activate
python -m pip install -r deckestra/skills/build-editable-decks/requirements-maintainer.txt
python deckestra/tools/release_gate.py deckestra --history --require-provenance
cd deckestra
```

The virtual environment is deliberately outside the repository because the
privacy gate rejects runtime environments inside the source tree. On Windows,
activate it with `deckestra-venv\\Scripts\\Activate.ps1`. If activation is not
available, use `deckestra-venv\\Scripts\\python.exe` for every Python command.
To install the validated core without the maintainer-only audit dependencies,
use `requirements-core.txt` instead.

Copy `skills/build-editable-decks` to one supported location:

| Scope | Destination |
|---|---|
| Current repository | `.agents/skills/build-editable-decks` |
| Current user | `$HOME/.agents/skills/build-editable-decks` |

For a user-scoped installation on macOS or Linux:

```bash
mkdir -p "$HOME/.agents/skills"
cp -R skills/build-editable-decks "$HOME/.agents/skills/build-editable-decks"
python "$HOME/.agents/skills/build-editable-decks/scripts/attribution_guard.py"
```

On Windows, copy the same folder to
`$HOME\\.agents\\skills\\build-editable-decks` and run
`python $HOME\\.agents\\skills\\build-editable-decks\\scripts\\attribution_guard.py`.

Install the reproducible core used by deterministic layout, validation, and
native PPTX export:

```bash
python -m pip install -r skills/build-editable-decks/requirements-core.txt
```

Keep this environment active when starting or restarting Codex so Skill
scripts use the same validated interpreter. Alternatively, install the core
requirements into the exact Python interpreter configured for Codex.

Install `skills/build-editable-decks/requirements.txt` only when you need its
optional document conversion, image-provider, narration, or editor
integrations. That convenience set is not part of the v0.1.0 validated
environment and includes separately licensed AGPL/LGPL packages; review
[`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md) first. Codex normally detects
Skill changes automatically; restart it if the Skill does not appear.

The GitHub repository is the auditable source distribution. Official OpenAI
guidance recommends a plugin when a Skill is packaged for broader installable
distribution or bundled with connectors; that is a separate distribution step,
not a hidden dependency of this source release.

## Use

Invoke it explicitly in Codex with `$build-editable-decks`, or select it with
`@` on a ChatGPT surface that exposes standalone Skills. Example requests:

```text
$build-editable-decks Turn this paper into a 12-page technical briefing for an executive audience.

$build-editable-decks 把这些材料整理成 15 页中文技术简报，保留数据来源，表格和图表必须可编辑。

$build-editable-decks Beautify this PPTX without changing its wording, page count, or order.
```

The Skill chooses one of four explicit routes: new deck generation, reusable
template creation, native PPTX filling, or native PPTX enhancement. Runtime
projects are always created outside the installed Skill directory.

## Privacy boundary

This source repository contains no user documents, uploaded images, real client
presentations, renderings, audio, runtime logs, or private evaluation cases.
Tests use synthetic text and programmatically constructed fixtures only.

The publication gate checks filename, magic bytes, embedded raster payloads,
secrets, private links, absolute paths, file provenance, and every reachable Git
blob. Blind-suite cases, renders, reviews, and evidence remain external. Runtime
processing is local by default; an external provider is used only for a
provider-dependent capability the user explicitly requests. Remote reference-
image editing additionally requires `--allow-remote-reference-upload`, and
remote-provider receipts log hashes and counts instead of prompt text, reference-
input paths, signed URLs, or response bodies. Ordinary local CLI output may show
the destination paths of files written inside the user's project.

See [`PRIVACY.md`](PRIVACY.md) and [`SECURITY.md`](SECURITY.md).

## Development and release gates

Install the pinned maintainer environment, then run the single read-only gate:

```bash
python -m pip install -r skills/build-editable-decks/requirements-maintainer.txt
python tools/release_gate.py . --history --require-provenance
```

The full gate above is the publication gate for the initial public source
release. GitHub Actions runs the same command on every push and pull request.
The private 1,000-case suite is not required for v0.1.0 and does not weaken or
skip any privacy, provenance, license, identity, syntax, test, or prompt audit.

After the future frozen blind evidence passes, a separately certified source
archive can be built at an absolute path outside the repository:

```bash
python tools/build_release.py . \
  --output /tmp/deckestra-source.zip \
  --certification-evidence /absolute/external/certification-runs/evidence.json
```

The builder refuses an in-repository archive, an existing destination, missing
provenance, forbidden reachable-history evidence, or incomplete certification.
It creates a byte-reproducible ZIP, extracts it into a temporary directory, and
reruns the complete worktree and certification gates against that exact copy.

Contributions must follow [`CONTRIBUTING.md`](CONTRIBUTING.md); real examples,
screenshots, uploaded media, and private fixtures are never acceptable test data.

## License and attribution

Deckestra source is licensed under the MIT License. Some conversion and
workflow components are included or adapted from `hugohe3/ppt-master` under
MIT; the complete upstream notice is preserved in
`third_party/ppt-master/MIT.txt`. Pinned Apache POI and Open XML SDK data retain
their own notices and licenses. Separately installed Python dependencies keep
their own licenses, including the copyleft terms identified in
[`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md). Deckestra is not an official
or endorsed upstream release.
