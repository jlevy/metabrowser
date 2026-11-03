---
type: is
id: is-01m6g4q0q0dvzhxj3yesx7qayg
title: "Diff view: report the file at the top of the pane, for the Pulls nav"
kind: feature
status: closed
priority: 2
version: 6
delegate: claude-code@spud10.local
labels: []
dependencies: []
parent_id: is-01m6f3n89kn7ztmfhrzswxnsgz
hold: null
hold_until: null
created_at: 2026-11-03T07:24:25.696Z
updated_at: 2026-11-03T20:17:10.182Z
started_at: 2026-11-03T08:05:59.084Z
closed_at: 2026-11-03T20:17:10.182Z
close_reason: "Completed by forward commits in the PR-support stack; independent reviews, rechecks and dispositions are published on the owning PRs. Final integration ea771741211193a387c1771e04df29b5a9698100 passed make verify (4712 Python, 9 expected skips, 373 transcripts), 8 public live tests, installed-wheel Chrome (22 actions, 25 unchanged checkout/Git fingerprints), and all 171 CI jobs across 19 current-head runs on 14 PRs. Final clean review: https://github.com/jlevy/metabrowser/pull/288#pullrequestreview-5758664799 . No PR merged."
resolution: null
duplicate_of: null
---
Requested by the Pulls tab's step 4 (mb-zx9q): 'the selection follows a reader who scrolls the diff by hand' needs the diff view to say which file is at the top of the pane, as an event or a fileAtTop() on the page handle beside scrollToFile and fileForPath (docs/large-content-rendering.md). Build it on PR 284's diff view after E1 (mb-ivvw) lands, because E1 changes which rows are drawn: the answer must name the file whose bar or reserved block is at the top, drawn or not, and must not force a draw. Pin it in tests/dom/diff-file-jump-session.js.

## Notes

2026-11-03: after E1 (9b624b3a), a ready file past the first screen settles lines one or two frames after a jump and can come back superseded (docs/large-content-rendering.md); a file-at-top answer has to work over held files too.

2026-11-03 independent-review integration at final tip 58270d69. Implemented public currentFile/onCurrentFile API in 0fce3ece with bisection over ordered sections, held/deferred support without drawing, coalesced reports, immediate subscription and disposal. Strong Review F and production diff sessions pass. The completed #287 tree follows current-file feedback without stealing focus; Chrome keyboard/scroll/Back checks pass. Final full verification, publication and remote CI are coordinator gates still pending; no PR merged.
