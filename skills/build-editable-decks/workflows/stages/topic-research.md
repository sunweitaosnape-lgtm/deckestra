---
description: Generate source-intake stage that fills externally verifiable factual gaps after explicit permission for external research.
---

# Topic Research Stage

> Factual preparation inside the active Generate profile's source intake.
> Run for topic-only input or blocking fact gaps only after explicit research
> permission. Output is a supplement plus stable fact provenance.

This stage supplies facts needed to build the requested deck. It does not select,
download, or generate images. Default Generate resolves image selection in the
final Strategist plan and acquires AI / web / slice assets after confirmation;
Quick Generate resolves them later in its resource-preparation phase, but it
cannot acquire an external resource without explicit permission.

## When to Run

| Material state | Action |
|---|---|
| Topic-only input or planning-critical factual gaps, with explicit research permission | Research only the externally verifiable facts required by the outcome |
| Supplied material already supports the requested outcome | Skip this stage and continue the active Generate profile's source preparation |
| External research permission is absent, or the user requires a closed corpus, source-only transformation, or no external enrichment | Do not browse. Ask once for explicit research permission or authoritative sources when the missing facts block the requested deck; otherwise stay within supplied material |

**Sufficiency test**: a gap exists when the deck would otherwise invent, omit,
or leave unsupported a required externally verifiable claim.

**Hard rule — preserve supplied facts**: supplement the user's material; never
silently replace it. Record a material source conflict in the research output
for the active content owner instead of choosing a different claim without
disclosure. Do not research omissions outside the requested scope.

**Hard rule — external research is opt-in**: topic-only input, missing facts,
quick mode, and a request to avoid confirmation do not imply permission to use
web search, fetch a new URL, or send a user-derived research query to an
external service. Permission must be explicit in the current request or obtained
with one research-boundary question. Supplying a URL explicitly permits fetching
that URL only; it does not grant open-ended research permission. Never send a
source document, extracted passage, uploaded image, or private path to a search
or research provider.

---

## Step 1: Define the gap brief

**Clarification boundary**: bundle missing scope and research permission into
one question. Quick uses local defaults but still stops for missing external
permission when facts block the outcome.

| Item | Default if unspecified |
|---|---|
| Topic | From the user request |
| Requested scope / outcome | From the user request; otherwise broad overview |
| Supplied-material baseline | Facts and claims already available |
| Research gaps | Only facts needed to support the requested outcome |
| External-source boundary | No external factual enrichment unless the user explicitly requested or approved it; supplied facts remain authoritative inputs |
| Output language | Match user input |
| Target audience / communication intent | Use what is explicit; Default leaves final confirmation to Strategist, while Quick resolves routine gaps in active context |
| Research stem (`<research_slug>`) | `<topic_slug>_research`; choose another unused snake_case stem rather than overwrite an existing file |

Do not repeat the full default-pipeline confirmation here. Default Generate
confirms the complete communication contract in Step 4; Quick Generate adds no
confirmation stage.

---

## Execution Context

**Default — isolated research when available**: The main agent owns the gap
brief. If an isolated worker has web/fetch access and declared-output write
access, dispatch one; otherwise run Steps 2–3 locally.

| Actor | Contract |
|---|---|
| Main agent | Supply outcome, source paths, gaps, language, two unused output paths, and this stage path |
| Research worker | Read this stage, follow Steps 2–3, write only the two outputs, acquire no images, and make no deck-design decisions |

**Hard rule — isolate retrieval, not research**: Raw pages and fetch transcripts
stay in the worker context. Its ≤250-word receipt contains status, paths, gap
counts, fact count, and conflicts. After import, read both complete artifacts;
never use the receipt as deck content.

**Validation**: Before import, the main agent verifies both exact files exist, the Markdown contains `## Research Brief` and `## Sources`, the JSON parses with schema `deckestra.fact-provenance.v1` and unique sequential IDs, and the two files agree. Return an invalid pair to the research worker for owning-artifact repair; use main-context web research only when isolated execution is unavailable.

---

## Step 2: Gather factual sources

Use the web search and fetch tools available in the active research context. An isolated worker without them returns `blocked: web-tools-unavailable`. If no usable research context has search/fetch tools, the main agent pauses and asks the user for authoritative URLs covering the declared gaps, then fetches each with:

```bash
python3 ${SKILL_DIR}/scripts/source_to_md/web_to_md.py <URL>
```

| Phase | Action |
|---|---|
| Orient | Search only far enough to map authoritative sources to the declared gaps |
| Deep fetch | Read the highest-signal primary or authoritative pages in full |
| Targeted fill | Search only for gaps still unsupported after those reads |

| Priority | Source |
|---|---|
| 1 | Primary sources, official sites, institutional releases, standards, or original research |
| 2 | Authoritative reference works and reputable academic sources |
| 3 | Reputable reporting or analysis when primary evidence is unavailable |
| Avoid | Unsourced reposts, unverifiable summaries, and stock-aggregator pages |

**Stop condition**: stop when every declared gap has enough sourced evidence for
the active content owner to decide whether and how to include it. Do not expand
into unrelated overview / history / outlook sections merely to make the
research look complete.

---

## Step 3: Save the factual supplement

Write two artifacts under `projects/`:

| Artifact | Path |
|---|---|
| Research supplement | `projects/<research_slug>.md` |
| Fact provenance | `projects/<research_slug>.facts.json` |

**Hard rule — location and preservation**: write both files under `projects/`, never the repository root. Do not overwrite an existing user file; choose a new research stem instead. This stage creates no image folder.

Begin the research Markdown with a compact `## Research Brief` containing the supplied-material baseline, declared gaps, audience / intent already known, and requested outcome. Organize the body by gap, include concrete facts only, flag material conflicts, and end with `## Sources` listing every URL used.

Write every externally sourced claim that may enter the deck to `<research_slug>.facts.json` with a stable sequential ID, especially quantitative, date, ranking, attribution, and named-entity claims. Do not include user-supplied claims or invented scenario values. When no external claim is retained, write the schema with an empty `facts` array.

```json
{
  "schema": "deckestra.fact-provenance.v1",
  "topic": "<topic>",
  "facts": [
    {
      "fact_id": "F001",
      "claim": "One concise, presentation-ready factual claim",
      "source_title": "Authoritative page title",
      "source_url": "https://example.org/source",
      "classification": "external",
      "retrieved_at": "YYYY-MM-DD"
    }
  ]
}
```

IDs are immutable within the file. Correct a claim under the same ID; never reuse a removed ID for a different fact. The research Markdown and provenance file must agree.

---

## Hand-off

Import the research supplement and provenance alongside any user-supplied
sources through the active profile's source intake:

```bash
python3 ${SKILL_DIR}/scripts/project_manager.py import-sources projects/<project_name> [<source_paths...>] projects/<research_slug>.md projects/<research_slug>.facts.json
```

The imported pair remains evidence-facing context, not a locked presentation
contract. Default Generate has Strategist read both files completely before
confirmation and use them to select the content, page roster, and image resource
plan. Quick Generate has the current agent read both completely before its
active-context content, design, and resource decisions.

```markdown
## ✅ Topic Research Complete
- [x] Research execution: <isolated worker | main-context fallback>
- [x] Research supplement: `projects/<research_slug>.md` (N declared gaps covered)
- [x] Fact provenance: `projects/<research_slug>.facts.json` (N external facts)
- [x] Artifact contract validated: `## Research Brief`, `## Sources`, `deckestra.fact-provenance.v1`, unique sequential IDs, and Markdown/JSON agreement
- [x] No images acquired inside this factual-research stage
- [ ] **Next**: Default returns to [`generate-pptx`](../generate-pptx.md) Step 2; Quick returns to [`quick-generate`](../profiles/quick-generate.md) §2. Import all source artifacts, then fully read the imported research pair before planning or direct SVG authoring
```
