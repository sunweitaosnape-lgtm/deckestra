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

## PPTX delivery regressions

The release gate discovers `tests/test_pptx_delivery_check.py` automatically.
It builds synthetic packages in temporary directories and checks both status
and diagnostic codes for truncation, corrupt ZIP data, content types, broken
relationships, duplicate parts, malformed XML, and CLI failures. No binary
fixture or generated presentation belongs in the repository.

`tests/test_deterministic_layout.py` reuses the native table/chart export smoke
fixture. It rereads the actual export with python-pptx and checks slide count,
table cells, chart categories, and series values. Its separate LibreOffice test
imports and resaves that export with an isolated temporary profile, then checks
the new package and its native content. A zero process exit code alone is not
accepted. The input file must remain unchanged.

Local runs report an explicit skip when LibreOffice is not installed. To require
the application check, set `DECKESTRA_REQUIRE_LIBREOFFICE=1`. The release workflow
installs LibreOffice Impress and sets this flag, so a missing executable fails
CI. Run the normal release gate rather than a separate list of delivery tests.

These checks establish different facts. Package validation detects structural
damage; python-pptx rereading checks a second parser; LibreOffice import/resave
checks that application's acceptance of a small synthetic deck. None proves
Microsoft PowerPoint opening without repair, visual fidelity, font availability,
or preservation of every supported feature. PowerPoint still requires testing
on a host with that application installed.

Download-link expiry, authentication, and incomplete HTTP transfer are separate
delivery concerns. The tests do not contact download URLs. A saved HTML error
response is rejected as a non-ZIP file, but its transport cause is not inferred.
