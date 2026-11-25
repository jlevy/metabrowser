---
type: is
id: is-01m88075nzr5jqhrr63cawrq0w
title: Guided review steps draw whole-file documents through the diff view's rendered layer and chooser
kind: feature
status: closed
priority: 2
version: 7
delegate: claude-code@spud10.local
labels: []
dependencies: []
parent_id: is-01m8806zrnxn9jwj89hffd2yv7
hold: null
hold_until: null
created_at: 2026-11-25T00:03:20.371Z
updated_at: 2026-11-25T06:36:11.740Z
started_at: 2026-11-25T00:12:07.035Z
closed_at: 2026-11-25T06:36:11.737Z
close_reason: "Merged in #806 (main 1f23640)"
resolution: null
duplicate_of: null
---

## Notes

PR #806 (https://github.com/jlevy/metabrowser/pull/806), the top layer of native stack #809 above #807 (base claude/guided-review-groups). Entry point: diff/index.js mountRenderedFile beside mountFilePatch; the page binds it to DOCS_DRAWING for Markdown and CHANGES_DRAWING for YAML and JSON in pull-page.js (Docs lists only the docs group). One-file read by path (comparison route file=<path>); its manifest entry carries the id the rendered route takes.

Review A (https://github.com/jlevy/metabrowser/pull/806#pullrequestreview-6050259425): the guided route now decides which whole-file references are documents with the rendered route's own rule (rendered_format in pull_rendered_diff.py, both sides of the change), answers each reference's `rendered` format, hydrates no patch for a document and charges it nothing against MAX_STEP_PATCH_BYTES; the route golden pins a document past that budget answering ready. A rejected render keeps the guide's bar above the view's one-sentence notice. A8 (rebase) declined: this repository merges layers' bases, never rebases or force-pushes.

Deferred, candidates for beads: Open full diff on a drawn document (only a failed one keeps the guide's bar); per-document Diff|Current toolbar and N key (first in page wins); no prefetch of the next step's documents. Follow-up from review A: Docs holds its first screen out of sight while its rendered Markdown waits (github-pull-diff-holding and the firstScreen race in pull-page.js, bounded by CHANGES_FIRST_SCREEN_MS); a step's document gets only the view's per-file markdownHoldMs, not that page-level hold, so its bar and toolbar can show before its first screen's Markdown arrives, and if mb-qn7e's Full | Concise decision relies on the page hold, a step will not get it. Decide whether the step should share Docs' hold.

Earlier: fixed a broken relative link in the plan (from base commit ae5e17d9b) and moved the plugins.md SDK note off main's rewritten export sentence.
