# Changelog

All notable public changes to Deckestra are documented here.

## [Unreleased]

## [0.1.0] - 2026-08-08

### Added

- Initial public source release of the `build-editable-decks` Skill.
- Four explicit presentation routes for generation, reusable templates, native
  PPTX filling, and native PPTX enhancement.
- Twelve deterministic editable layout families with bounded repair and
  content-free layout traces.
- Native editable table and chart export in the deterministic layout path.
- Full-history privacy, secret, provenance, identity, and third-party license
  gates using synthetic tests only.
- A pinned upstream path/blob map for every retained MIT-adapted Skill file.
- GitHub Actions validation on every push and pull request.

### Removed

- The captured `pptx_animation_presets.json` registry is excluded from the
  public tree and reachable history because its PowerPoint capture and
  redistribution provenance was insufficiently documented. Object-animation
  authoring now fails closed; page transitions, Morph, and structural
  preservation checks for existing timing XML remain available.

### Certification status

- The 1,000-case `zh-cn-tech-brief-15-v1` blind evaluation remains a future
  certification target. v0.1.0 makes no 99% completion-rate claim.

[Unreleased]: https://github.com/sunweitaosnape-lgtm/deckestra/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/sunweitaosnape-lgtm/deckestra/releases/tag/v0.1.0
