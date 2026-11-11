---
type: is
id: is-01m74qv7hbqxtkan4pevshgfq8
title: "PR #347 (merge): feat(pulls): open exact revision files from Changes"
kind: task
status: closed
priority: 1
version: 8
labels: []
dependencies: []
parent_id: is-01m74qv6pggjrpe3kkqbtj01g3
child_order_hints:
  - is-01m74vwmegp0f11eb7vj9pnq0t
  - is-01m753phnahw8439f040swe73f
  - is-01m75843dp8xrq74kap2tsr2b6
  - is-01m7584qkw8sr4z3rn6rhd610h
created_at: 2026-11-11T07:23:35.338Z
updated_at: 2026-11-11T16:41:47.505Z
closed_at: 2026-11-11T16:41:47.504Z
close_reason: "Landed on main in ab346bf8 via native stack #350 merge (2026-11-11). Reviews and dispositions recorded in the bead notes; merge gate passed with CI 9/9 at the final head."
resolution: null
duplicate_of: null
---

## Notes

Reviews: A senior r1 (review-5855504972) -> reply issuecomment-6792932299; B security r1 (review-5855525387) -> issuecomment-6792932708; C correctness r1 (review-5855769655) -> issuecomment-6792933182; D follow-up r2 (review-5857531488) -> issuecomment-6794752881; E follow-up r3 (review-5858411904) -> issuecomment-6796064167. A14 declined (kept with a test); everything else fixed. Final head e62e2b6b7c65e53dce150dfe716d745470822486, contains #346 6d924fd3, CI run 43020323646 green. No further round: r3 was Low-only; coordinator read the one sanitizer-adjacent change (inert_html.kpress_prose re-serializes hardened output with escaping and adds three fixed classes). Awaiting the stack merge gate.
