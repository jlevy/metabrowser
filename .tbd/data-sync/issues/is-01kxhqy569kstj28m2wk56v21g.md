---
type: is
id: is-01kxhqy569kstj28m2wk56v21g
title: "PR #1 review R4: parse gzipped Markdown frontmatter"
kind: bug
status: closed
priority: 1
version: 4
labels:
  - pr-review
  - metabrowser
dependencies: []
parent_id: is-01kxhpk3s4ffm69y00gc20pccg
created_at: 2026-07-15T01:58:20.616Z
updated_at: 2026-07-15T02:21:50.952Z
closed_at: 2026-07-15T02:21:50.952Z
close_reason: "Resolved on MetaBrowser PR #1 with red-first regression coverage, complete local verification, per-thread replies, and thread resolution. Latest head dfcd83e has all repository checks green and no unresolved review threads."
---
Resolve review thread PRRT_kwDOTX174c6Q9B4o across src/metabrowser/file_kinds.py and the /api/file and /api/kpress/render call sites. FileContext must parse logical Markdown frontmatter from gzip artifacts so response metadata and frontmatter-driven classification match plain .md behavior.

## Notes

Red endpoint tests confirmed gzip Markdown frontmatter was omitted from /api/file classification and passed as None to KPress. Added a FileContext-level gzip Markdown parser that reads through ArtifactPath, preserves frontmatter-format YAML parsing and error semantics, and therefore fixes both call sites plus plugin classification. Focused frontmatter/KPress/plugin slice: 23 passed; Ruff, BasedPyright, and formatting clean. Complete make verify under Node 24.18.0: 623 tests, all language/doc/public-hygiene gates and dependency audits clean, distribution build and isolated install checks passed.
