---
type: is
id: is-01kxhrcsdpqtncr8kgjmhwm8qf
title: "PR #1 review R6: preserve gzip transparency in KPress export"
kind: bug
status: closed
priority: 1
version: 4
labels:
  - pr-review
  - metabrowser
dependencies: []
parent_id: is-01kxhpk3s4ffm69y00gc20pccg
created_at: 2026-07-15T02:06:20.085Z
updated_at: 2026-07-15T02:21:50.968Z
closed_at: 2026-07-15T02:21:50.968Z
close_reason: "Resolved on MetaBrowser PR #1 with red-first regression coverage, complete local verification, per-thread replies, and thread resolution. Latest head dfcd83e has all repository checks green and no unresolved review threads."
---
Resolve review thread PRRT_kwDOTX174c6Q9F9y at src/metabrowser/server.py:1493. /api/kpress/export must pass decompressed source content and a logical source path to KPress so gzip-backed Markdown exports match preview and render without losing relative-asset resolution.

## Notes

Red regression against KPress 0.2.1 confirmed gzip Markdown export passed compressed bytes to KPress and raised UnicodeDecodeError. Added the optional host-decoded source_text seam in KPress PR #20, published and independently verified KPress 0.2.2, then pinned MetaBrowser to that public wheel. Gzip export now supplies decompressed text with the logical .md path so sibling assets resolve. PyPI wheel SHA256 46c3e9f0496f30d7e5c19c08c38a96634bee257af15124da0795fa267e9698e1; sdist SHA256 475f78dde2cd762f40add1351e3ca49b6c186182b2ef6fe1f8069182e14fb2cc. Complete make verify: 625 tests and all package gates passed.
