---
type: is
id: is-01kzsb4k9hwrt25jj9j6svkvaf
title: "Repository library Phase 1B-b: URL open, web-URL reduction, and serving (trust-gated)"
kind: task
status: open
priority: 1
version: 13
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
  - type: blocks
    target: is-01m2h7gjc36fqv8cv38qd9zynr
parent_id: is-01kzs5m38dz1egphfwf30c8h7n
created_at: 2026-08-11T21:19:59.280Z
updated_at: 2026-09-15T00:31:44.048Z
extensions:
  linear:
    id: 04c1dc4d-0602-449f-95a5-09481c36a843
    linked_at: 2026-08-16T08:05:43.432Z
---
Change the CLI root boundary from Path or None to str or None so URL syntax survives Typer. Detect conservative HTTPS, SSH, and explicit file:// Git sources before local path resolution; reject credentials, unsafe transports, option-like inputs, and unsupported web namespaces; then clone or reuse an exact generic cache entry. Dispatch hosted web URLs through the provider-neutral reducer seam mb-12cz, retaining ref/path candidates, PR numbers, and meaningful line/query intent without teaching the cache GitHub. A repository-root cache hit serves gitroot with no network, provider credential lookup, or provider record. Force the untrusted profile once mb-vib1 lands; selected non-default branches are the separately testable mb-2xq7 slice.
