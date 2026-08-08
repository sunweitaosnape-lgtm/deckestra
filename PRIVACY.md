# Privacy boundary

This public source tree must never contain user-provided documents, images,
presentation files, extracted text, generated presentations, renderings,
voice tracks, runtime logs, or private evaluation cases.

The release gate rejects media and office-document formats by both filename and
file signature. It also rejects embedded raster payloads, credentials, private
runtime links, absolute local paths, symbolic links, undeclared files, and the
same material in reachable version history.

All public tests use synthetic text and programmatically constructed fixtures.
Runtime projects must be created outside the Skill package and remain excluded
from source control. A release candidate is invalid unless the privacy gate
passes on both its current tree and its complete publishable history.
