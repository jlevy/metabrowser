---
type: is
id: is-01m6h9ce663frjs7y677k6xf8w
title: "PR #287 Qodo4458535282: discard pending file jump when leaving Files"
kind: bug
status: closed
priority: 3
version: 3
labels: []
dependencies: []
parent_id: is-01m6g59qm4ewjgek4vjmndcxrj
created_at: 2026-11-03T18:05:16.357Z
updated_at: 2026-11-03T20:17:09.823Z
closed_at: 2026-11-03T20:17:09.823Z
close_reason: "Completed by forward commits in the PR-support stack; independent reviews, rechecks and dispositions are published on the owning PRs. Final integration ea771741211193a387c1771e04df29b5a9698100 passed make verify (4712 Python, 9 expected skips, 373 transcripts), 8 public live tests, installed-wheel Chrome (22 actions, 25 unchanged checkout/Git fingerprints), and all 171 CI jobs across 19 current-head runs on 14 PRs. Final clean review: https://github.com/jlevy/metabrowser/pull/288#pullrequestreview-5758664799 . No PR merged."
resolution: null
duplicate_of: null
---
Low https://github.com/jlevy/metabrowser/pull/287#discussion_r4458535282, review5757123686 at38ab13f1f8693a1b0478490258a35a7317ac1df9. pull-page.showFile keeps wantedFile while diff mount waits; Conversation disposal does not clear it, so later fileless Files visit can consume an abandoned path. Add deferred-mount navigation regression and preserve replacement remount/newest live file semantics. Root owns integration, publication, closure and sync.

## Notes

Confirmed/fixed in f1ae7c61188a85c319cf3870cacb32bc62402a0b, direct38ab13f1. Non-Files paint and page disposal clear wantedFile; generic disposeDiff stays unchanged. Red deferred mount retained src/app.txt into later fileless Files visit. Green controlled mount cases discard abandoned selection while retaining wanted file through temporary unavailability and same-Files replacement. Existing production route/history/mount controls unchanged and passing.81affectedpytest+24unchangedgoldens+full lint/types/parity+normalhooks pass. Exact evidence ready-state-287-38ab13f1/REPORT.json. Independent recheck/root integration/finalCI pending; root owns publication, closure and sync.
