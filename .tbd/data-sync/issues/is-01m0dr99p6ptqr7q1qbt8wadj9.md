---
type: is
id: is-01m0dr99p6ptqr7q1qbt8wadj9
title: "Parser ingest: GIT binary patch payloads, and pin format-patch framing with a test"
kind: feature
status: open
priority: 2
version: 2
spec_path: docs/project/specs/active/plan-2026-08-17-general-diff-rendering.md
labels: []
dependencies: []
parent_id: is-01kxse0d3sm8h0p1yh1mjwgbxz
created_at: 2026-08-19T19:34:33.413Z
updated_at: 2026-11-14T18:43:44.775Z
---
Ingest gaps in parse_unified_patch (src/metabrowser/diff/adapters/patch_file.py), from docs/project/research/research-2026-08-19-file-patch-formats.md.

1. GIT binary patch sections (literal and delta, base85 plus deflate, forward and reverse hunks) are marked binary with their content dropped. Ingest them to inline content refs so binary changes survive the patch path, bounded by size caps.
2. git format-patch mbox framing. Rechecked 2026-11-14: a format-patch with From/Subject headers and a trailing '-- ' signature parses with every file ready, because hunk counts bound each body. No test pins this. Add a hostile-input case with the three-dash separator and the signature, beside the existing ones.

Dropped: GitHub REST bare hunks. The GitHub plugin reads pull request changes over Git transport and ignores the REST patch field (builtin_plugins/github/pull_files_refresh.py), and mb-6394 closed on that design.
