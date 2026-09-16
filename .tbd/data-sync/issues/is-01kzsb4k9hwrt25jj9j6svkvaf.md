---
type: is
id: is-01kzsb4k9hwrt25jj9j6svkvaf
title: "Repository library Phase 1B-b: URL open, web-URL reduction, and serving (trust-gated)"
kind: task
status: in_progress
priority: 1
version: 16
spec_path: docs/project/specs/active/plan-2026-08-11-open-repo-from-git-url.md
delegate: codex@spud10
labels:
  - release:v0.11.0
dependencies:
  - type: blocks
    target: is-01kzt6hdasbhx6maqzvtxntxj7
  - type: blocks
    target: is-01m10vgv018nef5svd0kb54gv9
  - type: blocks
    target: is-01m10vgwqwn8gjdv8fm183vztr
  - type: blocks
    target: is-01m2h7gjc36fqv8cv38qd9zynr
  - type: blocks
    target: is-01m2kw2b66x74xxjjtdp3wrsr4
parent_id: is-01kzs5m38dz1egphfwf30c8h7n
hold: null
hold_until: null
created_at: 2026-08-11T21:19:59.280Z
updated_at: 2026-09-16T21:11:31.965Z
started_at: 2026-09-16T21:10:44.828Z
extensions:
  linear:
    id: 04c1dc4d-0602-449f-95a5-09481c36a843
    linked_at: 2026-08-16T08:05:43.432Z
---
Change the CLI root boundary from Path or None to str or None so URL syntax survives Typer. Classify safe Git sources before Path construction; dispatch provider web URLs through mb-12cz while retaining ref/path, provider target, and line/query intent. Acquire or reuse a shared repository store, resolve the default full OID, and serve a GitRevisionSubject through the content-source lifecycle with no network or provider credential lookup on a hit. Force the untrusted profile. Non-default branch integration remains mb-2xq7.
