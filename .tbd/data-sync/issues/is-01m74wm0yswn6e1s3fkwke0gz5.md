---
type: is
id: is-01m74wm0yswn6e1s3fkwke0gz5
title: "PR #349 A12: the generic diff plugin hard-codes the GitHub snapshot route"
kind: bug
status: closed
priority: 2
version: 2
labels: []
dependencies: []
parent_id: is-01m74wk8dt7weq5cmkt2hmdrjr
created_at: 2026-11-11T08:47:02.104Z
updated_at: 2026-11-11T12:33:47.429Z
closed_at: 2026-11-11T12:33:47.428Z
close_reason: "A12 fixed in c448aae8: diff-markdown.js and index.js name no GitHub route; rendered_route and snapshot_route come from the envelope; snapshotTargets(route) checks links against the comparison's own snapshot route."
resolution: null
duplicate_of: null
---
Severity: Low. PR #349 review: https://github.com/jlevy/metabrowser/pull/349#pullrequestreview-5855490584. References: diff-markdown.js:4, 66-85. Addressed on PR #349 (branch codex/pr-rendered-markdown-diffs).
