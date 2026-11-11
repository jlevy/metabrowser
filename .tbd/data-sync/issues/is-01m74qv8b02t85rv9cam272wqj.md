---
type: is
id: is-01m74qv8b02t85rv9cam272wqj
title: "PR #349 (merge): feat(pulls): render Markdown redlines in Changes"
kind: task
status: closed
priority: 1
version: 8
labels: []
dependencies: []
parent_id: is-01m74qv6pggjrpe3kkqbtj01g3
child_order_hints:
  - is-01m74wk8dt7weq5cmkt2hmdrjr
  - is-01m75bmvxx4egd93b4ggyde6k2
  - is-01m75ctrr5888kr3hwzkeezxc3
  - is-01m75hdkcm07rrqnt7wf1cqsgg
created_at: 2026-11-11T07:23:36.159Z
updated_at: 2026-11-11T16:41:48.240Z
closed_at: 2026-11-11T16:41:48.239Z
close_reason: "Landed on main in ab346bf8 via native stack #350 merge (2026-11-11). Reviews and dispositions recorded in the bead notes; merge gate passed with CI 9/9 at the final head."
resolution: null
duplicate_of: null
---

## Notes

Reviews: A senior, B security, C performance (r1); D follow-up correctness, E follow-up safety+performance (r2); F follow-up (r3). Replies at 59ad56cc: A issuecomment-6800979792, B -6800980210, C -6800980588, D -6800981087, E -6800981555, F -6800982067. All findings fixed (D8 by correcting the comment, coordinator-approved). Coordinator decisions: projection child process with -I and fixed cwd; private KPress functions under the exact pin, tracked as mb-x0sv; added-fence info strings exempt only for exact Pygments aliases plus a short list; pygments declared directly (SUPPLY-CHAIN-SECURITY entry). Final head 59ad56cc010e45bf039c9d431dadabfbc638b030, contains #348 f959206b, CI run 43053293968 green.
