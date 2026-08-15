---
type: is
id: is-01m03tsgt14c397j4s0q8q8qdp
title: "Content typing: widen beyond the text/binary split"
kind: feature
status: open
priority: 3
version: 1
labels: []
dependencies: []
created_at: 2026-08-15T23:05:57.824Z
updated_at: 2026-08-15T23:05:57.824Z
---
metabrowser.content_sniff answers one question — text or binary — because that is the only one needed to stop rendering small binaries as U+FFFD.

The layering anticipates more: classify_prefix takes bytes and returns a ContentClass, so recognizing further types (magic-number formats, encodings beyond UTF-8, shebang-based hints for extensionless scripts) means extending that function and the enum, not restructuring callers.

Do not widen this speculatively. Add a case when a view or rollup actually needs a distinction it cannot make today, and name that consumer — see AGENTS.md on speculative layers. Extension-based typing stays the primary path; content checks are the fallback for what extensions cannot answer.
