---
type: is
id: is-01m89etnezn85qys6s97krzkxg
title: "PR #834 B1: the plan says a {pull, path} reads the current comparison and an object reference costs a record read"
kind: task
status: closed
priority: 2
version: 3
delegate: claude-code@spud10
labels: []
dependencies: []
parent_id: is-01m89etmssv0xtt5xwa2qm5h2q
hold: null
hold_until: null
created_at: 2026-11-25T13:37:53.629Z
updated_at: 2026-11-25T14:05:20.904Z
started_at: 2026-11-25T13:37:58.229Z
closed_at: 2026-11-25T14:05:20.903Z
close_reason: "Fixed in 03a57880e on #834: the plan's {pull, path} row reads the kept manifest (not_cached without one) and the MAX_REFERENCES bullet names the per-kind measurement beside the constant. Disposition: https://github.com/jlevy/metabrowser/pull/834#issuecomment-7164727608"
resolution: null
duplicate_of: null
---
plan-2026-11-24-stack-review.md :332 and :356-357; correct to the kept manifest / not_cached and the bound measured per kind beside MAX_REFERENCES.
