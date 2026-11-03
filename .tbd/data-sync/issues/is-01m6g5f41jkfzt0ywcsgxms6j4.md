---
type: is
id: is-01m6g5f41jkfzt0ywcsgxms6j4
title: Repair overlay merge-base certainty and lender sweep edge cases
kind: bug
status: in_progress
priority: 1
version: 4
delegate: checkout_design
labels: []
dependencies: []
parent_id: is-01m6g59qm4ewjgek4vjmndcxrj
hold: null
hold_until: null
created_at: 2026-11-03T07:37:35.538Z
updated_at: 2026-11-03T08:26:06.156Z
started_at: 2026-11-03T07:38:10.112Z
---
Audit PR #283 at 483e3a83 and checkout draft #288. Preserve valid criss-cross merge bases on Git 2.43; reproduce timeout persistence and missing pack index sweep before focused fixes.

## Notes

Focused #283 commits a51cc866 (oldGit mergebase verification/typed bounds/missingrecord+shallow+temp cleanup),48c03f84 (bounded regular pack index validation/ref sweep refusal),6ade0868 (stale pin_changed error clears and comparison bound UI). Overlay120tests + finalrace regression passed; corrupt/absent index9tests and real indexv1/v2 accepted. UI failed502->pinchanged reproduction red then green; normalhooks pass. OldGit200khistory safetywalk median0.91s vs modern0.021s, modern path unchanged. ActualGit2.43 CI and root independent/final stack gates pending. Parent sync reserved.
