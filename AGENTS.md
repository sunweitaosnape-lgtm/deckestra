# Deckestra repository rules

Read [`skills/build-editable-decks/SKILL.md`](skills/build-editable-decks/SKILL.md)
and its [`workflows/routing.md`](skills/build-editable-decks/workflows/routing.md)
before changing presentation behavior. Read [`PRIVACY.md`](PRIVACY.md) before
adding files, fixtures, logs, examples, or release evidence.

Never place user inputs, extracted source text, uploaded images, generated
decks, slide renderings, audio, runtime logs, or private evaluation cases in
this repository. Use synthetic fixtures only. Keep runtime workspaces outside
the Skill package.

Before the first local commit and before every release candidate:

```bash
python tools/privacy_gate.py . --history --require-provenance
```

Do not initialize public history until identity cleanup and privacy scanning
pass. Do not add a network destination or publish anything before the release
plan authorizes it.
