---
type: is
id: is-01kzsb4k9hwrt25jj9j6svkvaf
title: "Repository library Phase 1B-b: URL open, web-URL reduction, and serving (trust-gated)"
kind: task
status: open
priority: 1
version: 11
spec_path: docs/project/specs/active/plan-2026-08-11-open-repo-from-git-url.md
labels:
  - release:v0.11.0
dependencies:
  - type: blocks
    target: is-01kzt6hdasbhx6maqzvtxntxj7
  - type: blocks
    target: is-01m10vgv018nef5svd0kb54gv9
  - type: blocks
    target: is-01m10vgwqwn8gjdv8fm183vztr
parent_id: is-01kzs5m38dz1egphfwf30c8h7n
created_at: 2026-08-11T21:19:59.280Z
updated_at: 2026-09-14T23:51:54.739Z
extensions:
  linear:
    id: 04c1dc4d-0602-449f-95a5-09481c36a843
    linked_at: 2026-08-16T08:05:43.432Z
---
Change the CLI root boundary from Path or None to str or None so URL syntax survives Typer. Detect conservative HTTPS, SSH, and explicit file:// Git sources before local path resolution; reject credentials, unsafe transports, option-like inputs, and unsupported web namespaces; then clone or reuse an exact generic cache entry. Reduce GitHub web URLs to a clone URL plus a typed selection using the shipped canonical URL codec and escaped inventory path identity, retaining PR numbers and meaningful line/query intent. A cache hit serves gitroot with no network, provider detection, or credential lookup. Force the untrusted profile once mb-vib1 lands and add CLI goldens and user docs; line highlighting may remain visibly unsupported until mb-281d rather than blocking repository opening.
