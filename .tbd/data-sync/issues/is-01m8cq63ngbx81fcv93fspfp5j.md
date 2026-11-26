---
type: is
id: is-01m8cq63ngbx81fcv93fspfp5j
title: Show the actual checked-out branch and follow external Git switches in Files
kind: bug
status: closed
priority: 2
version: 5
delegate: codex@spud10.local
labels: []
dependencies: []
parent_id: is-01m8cq5rvmb8jvrvqtqba4r980
child_order_hints:
  - is-01m8csf4ap1k7wkfyw84z1yw51
hold: null
hold_until: null
created_at: 2026-11-26T20:01:40.468Z
updated_at: 2026-11-26T21:05:02.343Z
started_at: 2026-11-26T20:02:12.669Z
closed_at: 2026-11-26T21:05:02.327Z
close_reason: "Implemented and independently reviewed in merged Metabrowser PR #892. Exact-head CI passed."
resolution: null
duplicate_of: null
---
The inspected checkout was correctly detached at 0047ed0. Verify attached branch naming, external switches, and detached fallback using independent fixtures.
