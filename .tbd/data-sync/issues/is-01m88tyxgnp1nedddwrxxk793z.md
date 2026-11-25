---
type: is
id: is-01m88tyxgnp1nedddwrxxk793z
title: "PR #822 A9: no test for the inert allowlist load fallback"
kind: bug
status: in_progress
priority: 3
version: 2
spec_path: docs/project/research/research-2026-11-22-annotated-collections-and-guided-pr.md
delegate: claude-code@spud10
labels: []
dependencies: []
parent_id: is-01m88tv745atsmky56h05dnn0f
hold: null
hold_until: null
created_at: 2026-11-25T07:50:41.426Z
updated_at: 2026-11-25T07:51:59.228Z
started_at: 2026-11-25T07:51:59.214Z
---
pull-page.js:8312-8320 throws when the allowlist did not load; guided-review.js:831-834 then shows notes as typed; the browserless session always provides MetabrowserInertHtml (tests/dom/github-guided-review-mount-behavior.js:174). Severity: Low. PR #822, review A: https://github.com/jlevy/metabrowser/pull/822#pullrequestreview-6053614872
