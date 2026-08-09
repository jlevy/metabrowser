---
type: is
id: is-01kzkv76p2eprd181arkqfj0we
title: "Address review: PR #22 — catalog authority, coverage semantics, activation paths"
kind: task
status: closed
priority: 1
version: 9
labels: []
dependencies: []
child_order_hints:
  - is-01kzkv7nkq736a52pyye0dedvs
  - is-01kzkv7p0czewd0fzphc929jjr
  - is-01kzkv7pffzt1eehwvcc7r09gb
  - is-01kzkv86t38ssk3x9wdr5ff80d
  - is-01kzkv876kex53a3ec4364kfm5
  - is-01kzkv87kexpva6h87zvnnrtwm
  - is-01kzkv880e2w7qad3tmdrs794w
created_at: 2026-08-09T18:05:35.297Z
updated_at: 2026-08-09T18:21:04.559Z
closed_at: 2026-08-09T18:21:04.558Z
close_reason: All seven findings (R7-R13) fixed in 5f711b8.
---
Senior engineering review of PR #22 at head 9b6baea, verdict changes-requested. Findings R7-R13 in https://github.com/jlevy/metabrowser/pull/22#issuecomment-5232913703

R1-R6 from the earlier cursor[bot] pass are already dispositioned (R1 rebuttal agreed by the reviewer, R3/R4/R5/R6 fixed); R2's stale-row rebuttal is superseded by R11.

The reviewer's architectural note: one map entry plus one boolean complete flag cannot represent authoritative-feed membership, passive observation, explicit-navigation exceptions, ignored-state policy, and cap truncation at once. Per-path provenance plus an epoch-aware feed state would resolve R7, R8, and R10 together.
