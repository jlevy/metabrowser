---
type: is
id: is-01m7hfn7p28nf9c2cswdkczx3g
title: "PR #470 A14: unify the commit page's summaryHost with the pull page's summary mechanism"
kind: task
status: open
priority: 3
version: 4
delegate: claude-code@spud10
labels: []
dependencies: []
parent_id: is-01m7wys8y3epj61gncgjakhsd0
hold: null
hold_until: null
created_at: 2026-11-16T06:10:37.889Z
updated_at: 2026-11-20T17:10:16.024Z
started_at: 2026-11-16T06:42:55.533Z
---
Suggestion. The commit page hands the diff a place outside its container (summaryHost); the pull request page draws through the view's summary. Unify on view.summary so summaryHost leaves diff-view.js and index.js and the renderer stays inside its container (docs/plugins.md:452). Severity: Suggestion. PR #470, review A round 1: https://github.com/jlevy/metabrowser/pull/470#pullrequestreview-5915665462

## Notes

Deferred from review A of PR #470 (dispositions at fcba106). Landed there: docs/plugins.md names summaryHost as the renderer contract's one exception (fcba106). Remaining: move the commit page to the pull request page's mechanism (render with summary: false, then view.summary(place, {raw, openFile}) awaited in mountCommitDiff before the handoff, its openFile jumping the commit's own diff), carry the commit's summaryTotals (added in 71b51dc for a truncated commit) to view.summary, and then drop summaryHost from diff-view.js, index.js, types.d.ts, and the docs/plugins.md exception. Waits on: the stack landing, since #471 and #472 also change this code.
