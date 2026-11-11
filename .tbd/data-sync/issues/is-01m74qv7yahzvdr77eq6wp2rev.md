---
type: is
id: is-01m74qv7yahzvdr77eq6wp2rev
title: "PR #348 (merge): perf(pulls): coalesce cache and comparison preparation"
kind: task
status: open
priority: 1
version: 7
labels: []
dependencies: []
parent_id: is-01m74qv6pggjrpe3kkqbtj01g3
child_order_hints:
  - is-01m74w003xk59spnxy95gr9dss
  - is-01m7594pkfe0xdkwhjqrwwpxz2
  - is-01m75d7enb9z11kt1ge773zz3r
  - is-01m75ky4vdrf0qhqbhy15j46z4
created_at: 2026-11-11T07:23:35.752Z
updated_at: 2026-11-11T15:49:35.870Z
---

## Notes

Reviews: A senior, B correctness, C security, D performance (r1) -> replies issuecomment-6794942981/-6794943344/-6794943706/-6794944351; E follow-up correctness r2 (review-5858632040) -> issuecomment-6798381122; F follow-up performance r2 (review-5858785036, replacing a safeguard-stopped run) -> issuecomment-6798381842; G follow-up r3 (review-5860828559) -> issuecomment-6800373475. All findings fixed; #346 A8 (mb-6yf6) closed here. Coordinator decisions: idle preparation only with an attached store (D1); revision-page code fences render plain, removing Pygments from the untrusted render path (G1-G4); stoppable renderer follow-up mb-273l. Final head f959206bc6fa4633ff3f49f81a2ce7b21a1e6a5c, contains #347 e62e2b6b, CI run 43049647459 green. Awaiting the stack merge gate.
