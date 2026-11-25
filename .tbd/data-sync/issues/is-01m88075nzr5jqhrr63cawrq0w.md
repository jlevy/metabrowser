---
type: is
id: is-01m88075nzr5jqhrr63cawrq0w
title: Guided review steps draw whole-file documents through the diff view's rendered layer and chooser
kind: feature
status: in_progress
priority: 2
version: 4
delegate: claude-code@spud10.local
labels: []
dependencies: []
parent_id: is-01m8806zrnxn9jwj89hffd2yv7
hold: null
hold_until: null
created_at: 2026-11-25T00:03:20.371Z
updated_at: 2026-11-25T01:18:48.950Z
started_at: 2026-11-25T00:12:07.035Z
---

## Notes

PR #806 (https://github.com/jlevy/metabrowser/pull/806), base claude/guided-review-groups (phase 1, no PR yet, so not a formal GitHub stack; link with gh stack link once phase 1's PR opens). Entry point: diff/index.js loadRenderedFile beside mountFilePatch; the page binds it to DOCS_DRAWING in pull-page.js. One-file read by path (comparison route file=<path>); its manifest entry carries the id the rendered route takes, so the guided route answer is unchanged. Deferred, candidates for beads: Open full diff on a document; per-document Diff|Current toolbar and N key (first in page wins); format decided by path alone (rename across formats, symlink); whole-file hunks read twice (guided answer and one-file answer); no prefetch of the next step's documents. Also fixed a broken relative link in the plan (from the base commit ae5e17d9b; phase 1's branch still has it) and moved the plugins.md SDK note off main's rewritten export sentence. make verify not run locally (load average ~300); CI green incl. ci-ok and stack-integration at b249e08db; guided review published, all 9 steps ready.
