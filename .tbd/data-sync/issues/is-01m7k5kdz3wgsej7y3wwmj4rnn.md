---
type: is
id: is-01m7k5kdz3wgsej7y3wwmj4rnn
title: "PR #485 A7: The owner steps leave out key custody, the yearly renewal, and what to do after a leak"
kind: bug
status: closed
priority: 3
version: 3
spec_path: docs/project/specs/active/plan-2026-11-16-macos-app-publishing.md
delegate: claude-code@spud10.local
labels: []
dependencies: []
parent_id: is-01m7k1vctj6d370jg7hqdps4hk
hold: null
hold_until: null
created_at: 2026-11-16T21:53:21.890Z
updated_at: 2026-11-16T22:09:57.257Z
started_at: 2026-11-16T21:53:38.387Z
closed_at: 2026-11-16T22:09:57.255Z
close_reason: "Fixed in 83ef69fc3: .p8 custody in O2/O3 (one download, deleted after store-credentials, a separate CI key), .p12 and .p8 deleted in O4, annual O9 renewal and re-export, and a leak step."
resolution: null
duplicate_of: null
---
Low. PLAN:389-408, :540-541. Fix: .p8 and .p12 custody in O3 and O4; an annual O9 for renewal and re-export; an incident step (revoke the API key; have Apple revoke the certificate and its tickets). Review A (round 1) of PR #485: https://github.com/jlevy/metabrowser/pull/485#pullrequestreview-5928293258
