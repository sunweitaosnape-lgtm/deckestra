# Frozen blind certification target

Deckestra has one publication-quality target profile:
`zh-cn-tech-brief-15-v1`. It requires exactly 1,000 previously frozen blind
cases, 15 pages per case, at least 997 whole-deck passes, and two independent
full-page reviews for every page. A whole deck passes only when every automated
gate succeeds and all 15 pages pass every criterion in both reviews.

This directory contains policy only. Private prompts, source documents, case
manifests, generated presentations, page renders, review comments, receipts,
and runtime logs are forbidden in the repository and its Git history. The
external evidence file contains only opaque case/reviewer IDs, hashes, booleans,
and bounded counts; it must also remain outside the repository.

This future certification target does not block an ordinary public source tag
that makes no quality-rate claim. `tools/release_gate.py` governs that source
release. `tools/build_release.py` is reserved for a separately certified source
archive and therefore continues to require complete external blind evidence.

[`evidence.schema.json`](evidence.schema.json) documents the external machine
format. `tools/certification_gate.py` remains the semantic authority: it also
checks ordering, cross-hash closure, current Skill/dependency hashes, reviewer
separation, per-page verdict consistency, and the whole-deck threshold.

Validate an external evidence file with:

```bash
python tools/certification_gate.py \
  --evidence /absolute/external/certification-runs/evidence.json
```

The command emits only safe aggregate results. Until it passes against all
1,000 cases, 99% remains a target and must not be described as an achieved or
certified result. The release builder requires this same external evidence and
has no flag that skips the certification gate.
