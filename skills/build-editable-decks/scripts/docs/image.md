# Image Tools

> **Design boundary**: keep provider credentials explicit, keep in-pipeline
> acquisition manifest-driven, and treat external image references as authoring
> inputs while delivery writes self-contained SVG previews and native PPTX
> media.

Image tools cover formula rendering, prompt-based AI generation, web image search, image inspection, and Gemini watermark removal.

## `latex_render.py`

Manifest-driven LaTeX formula renderer. Default Generate has Strategist write
`images/formula_manifest.json` only after the user confirms a visibly disclosed
remote formula policy. Quick Generate must obtain the same explicit approval in
conversation. Every configured renderer is external and receives the declared
LaTeX; without approval, keep math as editable text or mark it `Needs-Manual`.
The script renders only declared formulas and writes dimensions back into the
manifest.

```bash
python3 scripts/latex_render.py <project_path> --dry-run
python3 scripts/latex_render.py <project_path> --allow-remote-formula-rendering
python3 scripts/latex_render.py <project_path> --allow-remote-formula-rendering --providers codecogs,quicklatex,mathpad,wikimedia
```

Manifest shape:

```json
{
  "providers": ["codecogs", "quicklatex", "mathpad", "wikimedia"],
  "items": [
    {
      "id": "formula_001",
      "latex": "E = mc^2",
      "display": "block",
      "color": "#1D1D1F",
      "background": "#FFFFFF",
      "transparent": true,
      "dpi": 300,
      "filename": "formula_001.png"
    }
  ]
}
```

Output files land directly under `project/images/`. Formula filenames should use a shared `formula_` prefix, e.g. `formula_001.png`. The default provider chain is `codecogs,quicklatex,mathpad,wikimedia`; each external provider is tried until one succeeds, and the winning provider is recorded back into the manifest. `--providers` or manifest-level `providers` may override the order. `--allow-remote-formula-rendering` is mandatory for every non-dry-run invocation and may be supplied only after explicit user approval. Formula PNGs are transparent by default. `background` is the temporary render matte and local background-removal reference; set `transparent: false` only when an opaque final formula asset is intentional. The script does not scan `spec_lock.md` or source documents for `$...$`; formula selection belongs to the active resource owner.

## `image_gen.py`

Unified image generation entry point.

This script is the **Path A** API/proxy executor for generated images. Default
Generate checks `design_spec.md §I / AI Image Acquisition Path` before manifest
mode: only `api` / `auto` permits Path A; a missing or unknown value fails
closed and returns to Step 4 recovery. Quick Generate has no Design Spec: use
the explicit active-context path when supplied. After the user has explicitly
approved AI-image acquisition, an unspecified implementation path may use
`auto` to select the A → B → C chain defined in
[`image-generator.md`](../../references/image-generator.md) §7 without another
interaction. Without that category permission, do not run this tool.
In either profile, `host-native` uses the host image tool directly and `manual`
uses the read-only Markdown sidecar.

```bash
python3 scripts/image_gen.py "A modern futuristic workspace"
python3 scripts/image_gen.py "Abstract tech background" --aspect_ratio 16:9 --image_size 4K
python3 scripts/image_gen.py "Concept car" -o projects/demo/images
python3 scripts/image_gen.py --list-backends
```

Backends are grouped into Core / Extended / Experimental tiers. Run `python3 scripts/image_gen.py --list-backends` for the current list.

Backend selection:

```bash
python3 scripts/image_gen.py "A cat" --backend openai
python3 scripts/image_gen.py "A cinematic portrait" --backend minimax
python3 scripts/image_gen.py "A product launch hero image" --backend qwen
python3 scripts/image_gen.py "科技感背景图" --backend zhipu
python3 scripts/image_gen.py "A product KV in cinematic style" --backend volcengine
```

Configuration sources:

1. Current process environment variables
2. The file explicitly named by `DECKESTRA_ENV_FILE`, when set
3. `~/.deckestra/.env`

Current-directory, clone-root, and installed-Skill `.env` files are not
discovered automatically.

The active backend must always be selected explicitly via `IMAGE_BACKEND`.

Example `.env`:

```env
IMAGE_BACKEND=openai
OPENAI_API_KEY=sk-xxx
OPENAI_MODEL=gpt-image-2
# Optional proxy
# OPENAI_BASE_URL=http://127.0.0.1:3000/v1
# OpenAI-compatible provider knobs:
# OPENAI_SIZE_PRESET=auto
# OPENAI_RESPONSE_FORMAT=auto
# OPENAI_QUALITY=auto
# Allowed values: png / jpeg / webp
# OPENAI_OUTPUT_FORMAT=png
# jpeg/webp only, 0-100
# OPENAI_OUTPUT_COMPRESSION=80
# gpt-image-2: auto / opaque
# OPENAI_BACKGROUND=auto
# auto / low
# OPENAI_MODERATION=auto
```

Example process environment:

```bash
export IMAGE_BACKEND=openai
export OPENAI_API_KEY=sk-xxx
export OPENAI_MODEL=gpt-image-2
export OPENAI_OUTPUT_FORMAT=png
```

Current process environment wins over `.env`.

OpenAI backend notes:
- `gpt-image-2` is the default OpenAI model.
- Requests are sent with plain `requests.post()` to improve compatibility with
  OpenAI-compatible proxies that block the OpenAI SDK's `httpx` transport.
- For `gpt-image-2`, `image_size=512px` means a low-quality draft preset, not a literal 512px edge. The model requires both edges to be multiples of 16px, a long:short ratio no greater than 3:1, and total pixels between 655,360 and 8,294,400.
- `OPENAI_BACKGROUND=transparent` is not supported by `gpt-image-2`; use `auto` or `opaque`.
- If `OPENAI_OUTPUT_FORMAT=jpeg` or `webp`, generated files use `.jpg` or `.webp` extensions instead of `.png`.
- OpenAI-compatible providers that reject OpenAI-specific fields can use `OPENAI_RESPONSE_FORMAT=omit`, `OPENAI_QUALITY=omit`, and `OPENAI_SIZE_PRESET=<preset>`. Valid response formats are `auto`, `b64_json`, `url`, and `omit`; valid size presets are `auto`, `legacy`, `gpt-image`, `gpt-image-2`, and `dall-e-2`.

Example `.env` for Agnes AI through the OpenAI-compatible backend:

```env
IMAGE_BACKEND=openai
OPENAI_API_KEY=your-agnes-key
OPENAI_MODEL=agnes-image-2.1-flash
OPENAI_BASE_URL=https://apihub.agnes-ai.com/v1
OPENAI_SIZE_PRESET=gpt-image-2
OPENAI_RESPONSE_FORMAT=omit
OPENAI_QUALITY=omit
```

Use provider-specific keys only (e.g. `GEMINI_API_KEY`, `OPENAI_API_KEY`). Run
`image_gen.py --list-backends` and use the provider-key table in this document
as the authoritative key-name reference.

`IMAGE_API_KEY`, `IMAGE_MODEL`, and `IMAGE_BASE_URL` are intentionally unsupported.

If you keep multiple providers in one `.env` or environment, `IMAGE_BACKEND` must explicitly select the active provider.

Recommendation:
- Default to the Core tier for routine PPT work
- Use Extended only when you need a specific model style
- Treat Experimental backends as opt-in

Example `.env` for MiniMax image backend:

```env
IMAGE_BACKEND=minimax
MINIMAX_API_KEY=your-api-key
# Optional: override base URL (defaults to https://api.minimaxi.com, domestic China endpoint)
# Use https://api.minimax.io for overseas access
# MINIMAX_BASE_URL=https://api.minimax.io
# MINIMAX_MODEL=image-01
```

## `analyze_images.py`

Analyze objective image-file facts in a project directory before writing the
design spec or authoring SVG.

```bash
python3 scripts/analyze_images.py <project_path>/images
```

The tool does not resolve a canvas or recommend a left/right, top/bottom, or
other slide layout. Its atomic CSV records EXIF-corrected native dimensions and
`AspectRatio`, the objective aspect-ratio category, optional source
`SourceDisplayRatio`, format, actual transparent-pixel presence, usage count,
and bitmap/vector capability facts. An empty folder rewrites a header-only
report; unreadable supported files still refresh the report and produce a
non-zero exit.

Use this as the default factual inventory; it does not perform semantic image
understanding or choose composition. Generate planning follows the Strategist's
context-first boundary: source context, captions / alt text / titles, filenames,
user notes, and existing resource records come first. Only an already-selected
provided/web asset whose focal-safe crop, overlay contrast, or quiet region
remains materially ambiguous may be inspected for that placement; this never
reopens selection or provenance, never bulk-opens the image folder, and never
restores routine readback of AI-generated images.

## `image_search.py`

Zero-config web image search across openly-licensed providers. Sister tool to `image_gen.py` — used when the resource list row has `Acquire Via: web`.

```bash
python3 scripts/image_search.py "offshore wind farm" \
  --filename cover_bg.jpg --slide 01_cover \
  --orientation landscape -o projects/demo/images
```

For multiple web rows, `--batch images/image_queries.json` searches them concurrently (modest default, `--concurrency N` / `IMAGE_SEARCH_CONCURRENCY` to tune) instead of one call per row — the web sister of `image_gen.py --manifest`. Schema and status semantics: [`image-searcher.md`](../../references/image-searcher.md) §5.

Providers (Pexels / Pixabay are tried first when keyed; Openverse and Wikimedia are zero-config fallbacks):

| Provider | Config | Strength |
|---|---|---|
| `pexels` | recommended: `PEXELS_API_KEY` | modern stock photography, people, workplace, lifestyle |
| `pixabay` | recommended: `PIXABAY_API_KEY` | broad type coverage including photos and illustrations |
| `openverse` | zero-config | fallback aggregator: Wikimedia + Flickr + museums + rawpixel |
| `wikimedia` | zero-config | educational, scientific, geographic, historical |

Default search chain (when `--provider` is unset): configured Pexels, configured Pixabay, Openverse, then Wikimedia. Missing keyed credentials are silently skipped. Keyed providers broaden stock-photo coverage but are optional; zero-config providers remain valid.

`image_search.py` uses the same private configuration boundary as `image_gen.py`: process environment, an explicit `DECKESTRA_ENV_FILE`, then `~/.deckestra/.env`. Skill installs can keep `PEXELS_API_KEY` / `PIXABAY_API_KEY` in the user-level file.

Query guidance:

Keep the Design Spec §VIII `Reference` as the full visual/crop intent; write a separate concise provider query for this CLI. Start with the shortest phrase that preserves identity, but retain exact multi-word names and necessary disambiguators beyond four words.

| Case | Pattern |
|---|---|
| Generic stock concept | `boardroom meeting` |
| China-specific landmark | Precise official place/identity name plus necessary geography |
| Avoid | Negative prompt wording such as `not tourist snapshot` |

License filter:

- **Default**: search all providers with `cc0,pdm,pexels,pixabay,cc by,cc by-sa` allowed together. The chosen image may be `no-attribution` or `attribution-required`; Executor adds an inline credit only when needed.
- `--strict-no-attribution` restricts the search to `cc0,pdm,pexels,pixabay` — useful for full-bleed hero images or templates that cannot host a credit element.

Pin a provider, refuse attribution, or override the manifest path:

```bash
# Pin Wikimedia
python3 scripts/image_search.py "Olympics opening ceremony" \
  --filename event.jpg --provider wikimedia \
  --orientation landscape -o projects/demo/images

# Strict mode — refuse CC BY / CC BY-SA
python3 scripts/image_search.py "abstract gradient" \
  --filename hero.jpg --strict-no-attribution \
  -o projects/demo/images
```

Suitability & manual replacement (a web top hit is metadata-relevant, not guaranteed visually right):

- By default only the best match is downloaded, plus a downscaled review copy at `images/.review/<stem>.jpg` (the placed asset stays full-resolution).
- For exact subjects (landmarks, people, companies, products), use `--require-terms` or batch `required_terms` so visually plausible but wrong metadata is rejected before ranking. Example: `--require-terms Chongqing --require-terms "Jiefangbei|Liberation Monument"`. Keep proper-name / geography anchors; do not broaden to generic terms like `canyon`, `stone pillar`, or `ancient town` just to improve coverage.
- `--save-candidates` (with `--max-candidates`, default 4) keeps an opt-in escalation pool under `candidates/<stem>/`; review it, then `--promote candidate_03.jpg --filename <name>.jpg`.
- `--from-url <url> --filename <name>.jpg` downloads a user-chosen image URL and replaces the target (recorded `license_tier: manual`) — the model-agnostic manual path; works even without a multimodal model.

Full review / escalation flow: [`image-searcher.md`](../../references/image-searcher.md) §5.

Output:

- Image saved to the specified output directory (auto-converts webp → jpg via Pillow when the filename extension demands)
- `image_sources.json` manifest with full provenance (provider, license, license_tier, author, source URL, dimensions, attribution_text)
- Manifest is idempotent on `filename` and written atomically; damaged existing provenance blocks replacement

Allowed licenses (default): CC0, Public Domain, Pexels License, Pixabay Content License, CC BY, CC BY-SA. Auto-rejected: CC BY-NC, CC BY-ND, CC BY-NC-SA, CC BY-NC-ND, all rights reserved, unknown.

The full role-level reference (intent → query translation, on-slide attribution contract) is in [`references/image-searcher.md`](../../references/image-searcher.md).

Deckestra does not include or recommend watermark-removal tooling. Use only
assets whose license and provider terms permit the intended presentation use,
and preserve required attribution or provider marks.
