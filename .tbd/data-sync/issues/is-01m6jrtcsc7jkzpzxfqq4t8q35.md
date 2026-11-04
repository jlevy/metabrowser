---
type: is
id: is-01m6jrtcsc7jkzpzxfqq4t8q35
title: Give paged PR file lists a stable identity for each refresh
kind: bug
status: closed
priority: 1
version: 3
delegate: codex@spud10
labels: []
dependencies: []
parent_id: is-01m6jhbnan8czw6c97gr5511mr
hold: null
hold_until: null
created_at: 2026-11-04T07:54:16.747Z
updated_at: 2026-11-04T13:48:45.075Z
started_at: 2026-11-04T07:56:27.424Z
closed_at: 2026-11-04T13:48:45.075Z
close_reason: The original feature-stack review, disposition, fix and publication scopes are complete. All21 requested feature PRs merged normally through native stacks278 and296, ending at main da87bb13c4434324af576b554711278139621b6b. Each owning fix and reviewed head is retained by ancestry; current-head CI and all exact publication/readback gates passed. The independently reproduced postlanding account-provenance bug remains open as mb-dvhc under mb-73n4, and the required documentation/skill/planning phase remains mb-ao35; this closure does not declare those later scopes complete.
resolution: null
duplicate_of: null
---
Dedicated correctness review reproduced a PR287 bug with validated backend publications and the production holder: two different same-length REST file lists can share second-resolution fetched_at, reader, listed_from and null base/head. The holder keeps before.js and continues at offset1 while the actual cache contains after.js. Add a stable explicit per-refresh list generation shared by every page, separate from display timestamps, update typed wire/frontend ownership and concise red-green controls for same-second replacement versus same-generation append. Fix in owning PR287 and merge forward; independently review and run required gates/CI. Do not mutate source while normal push session41771 runs.
