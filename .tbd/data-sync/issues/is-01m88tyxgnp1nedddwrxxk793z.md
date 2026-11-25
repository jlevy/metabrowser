---
type: is
id: is-01m88tyxgnp1nedddwrxxk793z
title: "PR #822 A9: no test for the inert allowlist load fallback"
kind: bug
status: closed
priority: 3
version: 3
spec_path: docs/project/research/research-2026-11-22-annotated-collections-and-guided-pr.md
delegate: claude-code@spud10
labels: []
dependencies: []
parent_id: is-01m88tv745atsmky56h05dnn0f
hold: null
hold_until: null
created_at: 2026-11-25T07:50:41.426Z
updated_at: 2026-11-25T08:58:04.434Z
started_at: 2026-11-25T07:51:59.214Z
closed_at: 2026-11-25T08:58:04.370Z
close_reason: "Fixed in d067c9779: the browserless mount session pins the fallback when the allowlist does not load. PR #822 review A dispositions: https://github.com/jlevy/metabrowser/pull/822#issuecomment-7157686246"
resolution: null
duplicate_of: null
---
pull-page.js:8312-8320 throws when the allowlist did not load; guided-review.js:831-834 then shows notes as typed; the browserless session always provides MetabrowserInertHtml (tests/dom/github-guided-review-mount-behavior.js:174). Severity: Low. PR #822, review A: https://github.com/jlevy/metabrowser/pull/822#pullrequestreview-6053614872
