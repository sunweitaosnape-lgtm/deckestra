# Contributing to Deckestra

Contributions are welcome only when they preserve the repository's clean-room
privacy boundary and the Skill's editable-output contract.

## Never submit private material

Do not add real presentations, source documents, uploaded images, screenshots,
page renders, audio, extracted text, customer names, local runtime paths,
credentials, private URLs, execution logs, blind-suite cases, or review evidence.
This prohibition includes deleted commits and force-pushable branch history.

Tests must use short synthetic text and programmatically constructed structures.
Do not “anonymize” a real file; create a new synthetic fixture from first
principles. Bug reports and pull requests must describe reproduction steps in
text and must not attach user artifacts.

## Change discipline

1. Read `AGENTS.md`, `PRIVACY.md`, and the affected route authority.
2. Keep runtime inputs and outputs outside the source tree.
3. Preserve native editability and fail closed on stale or incomplete evidence.
4. Update tests, prompt budgets, origin policy, and notices when applicable.
5. Never qualify a development result as a public pass-rate claim.

Before opening a pull request, run:

```bash
python3.12 -m venv ../deckestra-venv
../deckestra-venv/bin/python -m pip install -r skills/build-editable-decks/requirements-maintainer.txt
../deckestra-venv/bin/python tools/release_gate.py . --history --require-provenance
```

Keep the environment outside the source tree; the privacy gate rejects runtime
environments inside the repository. On Windows, use
`..\\deckestra-venv\\Scripts\\python.exe` in place of
`../deckestra-venv/bin/python`.

If an isolated environment is already active, the equivalent commands are:

```bash
python -m pip install -r skills/build-editable-decks/requirements-maintainer.txt
python tools/release_gate.py . --history --require-provenance
```

The frozen certification suite remains external. Contributors may improve its
public validator, but must not add cases, renders, comments, receipts, or raw
evidence to the repository.
