---
type: is
id: is-01m0ppz4jkc098qw35es5yd2vq
title: "H57: the server is no longer the bottleneck; the shell's own boot is, and it is unattributed"
kind: task
status: closed
priority: 1
version: 3
spec_path: docs/project/specs/active/plan-2026-08-21-load-time-performance.md
labels: []
dependencies: []
parent_id: is-01m0k5wh7jgr0dgs5y78kwwke1
created_at: 2026-08-23T07:04:41.810Z
updated_at: 2026-08-24T04:15:29.406Z
closed_at: 2026-08-24T04:15:29.406Z
close_reason: Startup attribution now splits bounded resource rows into response wait, Server-Timing work, and download. Exp-014 records the 22-request/154 KB shell and a representative app.js split; H10/H26 retain the remaining optimization question.
resolution: null
duplicate_of: null
---
On the fixed 246,282-file corpus this branch answers the first tree request in 6ms (tree_fetch_srv_ms, range 3-8) but does not paint a row until 276ms (first_row_ms, range 213-533). The ~270ms gap is the shell booting itself: 126 requests and 742KB transferred, of which 45KB is vendored library code.

Nobody has attributed that gap. It is now the ceiling on 'instant', and against the project's own principle -- never flash a spinner under ~50ms -- it is roughly 5x over budget.

Metric: a breakdown of navigation-to-first-row into DNS/connect, HTML, blocking CSS, JS parse, JS execute, and the inline render, at 1280x900 on the fixed corpus. Deliverable is the attribution, not a fix; the fix follows from which term dominates.

Relates to the asset loading tiers in docs/development.md.
