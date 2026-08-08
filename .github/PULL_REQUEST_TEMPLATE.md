## Scope

Describe the behavior changed and the synthetic verification performed.

## Required checks

- [ ] No user document, uploaded image, real deck, screenshot, render, audio,
      runtime log, private path, credential, or blind-suite artifact appears in
      this branch or its reachable history.
- [ ] All fixtures are synthetic and created from first principles.
- [ ] `python tools/release_gate.py . --history --require-provenance` passes.
- [ ] Third-party data, notices, and provenance origins remain correct.
- [ ] No unverified quality-rate or certification claim was added.
