---
type: is
id: is-01m7tb9zw4d1mkfhh9kbz4r7mk
title: "Host mode H6: sticky port per root, else an OS-chosen port the ready line reports"
kind: feature
status: open
priority: 2
version: 3
spec_path: docs/project/specs/active/plan-2026-11-18-host-mode.md
labels: []
dependencies:
  - type: blocks
    target: is-01m774re9ewc3k6c8hp5x78376
  - type: blocks
    target: is-01m748y1pa5yyy4wf2t16cpf0y
parent_id: is-01m748xpx7bjg68tfaf3q4nxmj
created_at: 2026-11-19T16:47:45.028Z
updated_at: 2026-11-19T16:49:49.414Z
---
Host mode plan step H6, its sticky-port part (docs/project/specs/active/plan-2026-11-18-host-mode.md, Implementation Plan and The Host Contract; Decisions HM-1 A and HM-6 A, taken 2026-11-19). Split from mb-qzny.

Delivers: a serve flag under which a server binds the port its root had last, else one the OS chooses, which the ready line (H2) reports, so a root keeps its origin across restarts. Where the port is remembered, in the root's recent target or a file of its own, is one of the plan's Open Questions. The app's relaunch (mb-w4kd) and the rootless spare (mb-bbod) use it. A golden and the reference-host test.

Slot: after H2; in Ordering 2, after Stack V, beside mb-54r1's reload on a new boot ID.
