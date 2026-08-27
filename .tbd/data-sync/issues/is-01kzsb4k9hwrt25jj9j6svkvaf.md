---
type: is
id: is-01kzsb4k9hwrt25jj9j6svkvaf
title: "Repository library Phase 1: URL root resolution and offline cache reuse"
kind: task
status: open
priority: 1
version: 6
spec_path: docs/project/specs/active/plan-2026-08-11-open-repo-from-git-url.md
labels: []
dependencies:
  - type: blocks
    target: is-01kzt6hdasbhx6maqzvtxntxj7
  - type: blocks
    target: is-01m10vgv018nef5svd0kb54gv9
parent_id: is-01kzs5m38dz1egphfwf30c8h7n
created_at: 2026-08-11T21:19:59.280Z
updated_at: 2026-08-27T05:40:23.105Z
extensions:
  linear:
    id: 04c1dc4d-0602-449f-95a5-09481c36a843
    linked_at: 2026-08-16T08:05:43.432Z
---
Change the CLI root boundary from Path or None to str or None so URL syntax survives Typer conversion. Detect supported Git URLs before local Path resolution; reject unsafe transports and credential-bearing or unsupported deep links; and resolve clone or exact cache hit before the existing serve path. Serve a validated cached gitroot without network access, report credential-free source identity, start backfill without holding first paint, force the untrusted profile once mb-vib1 lands, and add CLI goldens and user documentation. List, refresh, and purge management commands are Phase 2.
