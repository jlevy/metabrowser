---
type: is
id: is-01m74wkzcmtv9bnbzgpqny9e2d
title: "PR #349 A8: the Markdown module is imported only after the comparison arrives"
kind: bug
status: closed
priority: 2
version: 2
labels: []
dependencies: []
parent_id: is-01m74wk8dt7weq5cmkt2hmdrjr
created_at: 2026-11-11T08:47:00.499Z
updated_at: 2026-11-11T12:33:45.871Z
closed_at: 2026-11-11T12:33:45.870Z
close_reason: "A8 fixed in c448aae8: diff-markdown.js is imported beside the comparison request when the comparison names a rendered route; test tests/dom/diff-comparison-route-behavior.js."
resolution: null
duplicate_of: null
---
Severity: Low. PR #349 review: https://github.com/jlevy/metabrowser/pull/349#pullrequestreview-5855490584. References: index.js:336-348, 256-259. Addressed on PR #349 (branch codex/pr-rendered-markdown-diffs).
