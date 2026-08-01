---
type: is
id: is-01kyxrj3k0zm0d52vvjhnp4zzp
title: "Address review: PR #19 — KPress 0.3.0 upgrade"
kind: task
status: in_progress
priority: 1
version: 9
labels: []
dependencies: []
child_order_hints:
  - is-01kyxrjkwgephtr3dxkmka6qty
  - is-01kyxrjm4mvts4zh6cgp89tx5v
  - is-01kyxrjmcrtvgxez9y6xh067t7
  - is-01kyxrjmmqrya9f3tp76qcnnmv
  - is-01kyxrjmwxnyxnb3f59m7kf1jn
  - is-01kyxrjn4txakq9jwn5xhybs9d
created_at: 2026-08-01T04:15:49.343Z
updated_at: 2026-08-01T04:23:45.993Z
---
Address the senior engineering review posted at https://github.com/jlevy/metabrowser/pull/19#issuecomment-5149735316. Track R1-R5 plus accepted robustness suggestions, publish a per-finding disposition map, and return CI to green.

## Notes

R1-R4 fixed. S2 and S3 applied. S1 deferred to mb-1mrt as a focused supply-chain change. R5 closed mb-cq5z after splitting chart repaint to mb-ouhc. make verify passes with 743 pytest tests and 28 golden cases.
