# Runtime privacy rules

Keep every user project outside this Skill directory. Do not bundle, commit,
cache, or reuse user-provided or user-derived material. Use local processing by
default and invoke external content providers only for a capability the user
explicitly requested.

Remote image editing requires the separate
`--allow-remote-reference-upload` consent flag in addition to
`--reference-image`. Formula rendering sends selected LaTeX to an external
service and requires `--allow-remote-formula-rendering` after a visible,
explicit approval. Every TTS backend, including Edge, is remote; voice-catalog
queries and synthesis require `--allow-remote-tts`, and synthesis sends the
spoken notes text. Operational console receipts record only hashes, lengths,
counts, and status categories; remote-provider receipts do not print prompt or
formula text, reference-input paths, signed URLs, or remote response bodies.
Ordinary local CLI output may show destination paths for files written inside
the user's project.

Operational evidence may retain hashes, source identifiers, statuses, counts,
and bounded error categories. It must not retain source passages, media bytes,
credentials, private links, or hidden reasoning.
