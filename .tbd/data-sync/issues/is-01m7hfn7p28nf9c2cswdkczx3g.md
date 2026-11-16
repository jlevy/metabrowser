---
type: is
id: is-01m7hfn7p28nf9c2cswdkczx3g
title: "PR #470 A14: unify the commit page's summaryHost with the pull page's summary mechanism"
kind: task
status: open
priority: 3
version: 1
labels: []
dependencies: []
parent_id: is-01m7hcjv212191g3nw3tr8take
created_at: 2026-11-16T06:10:37.889Z
updated_at: 2026-11-16T06:10:37.889Z
---
Suggestion. The commit page hands the diff a place outside its container (summaryHost); the pull request page draws through the view's summary. Unify on view.summary so summaryHost leaves diff-view.js and index.js and the renderer stays inside its container (docs/plugins.md:452). Severity: Suggestion. PR #470, review A round 1: https://github.com/jlevy/metabrowser/pull/470#pullrequestreview-5915665462
