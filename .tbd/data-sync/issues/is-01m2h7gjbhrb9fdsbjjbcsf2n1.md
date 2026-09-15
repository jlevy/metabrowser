---
type: is
id: is-01m2h7gjbhrb9fdsbjjbcsf2n1
title: "GitHub Phase 3A: provider binding and repository summary snapshot"
kind: task
status: open
priority: 1
version: 2
spec_path: docs/project/specs/active/plan-2026-08-27-github-provider-and-pull-requests.md
labels:
  - release:v0.11.0
dependencies:
  - type: blocks
    target: is-01m2h7h50h2y8hhhq7x7f1zcmd
parent_id: is-01m10xd666fefs5z7ft5m58zj0
created_at: 2026-09-15T00:29:47.247Z
updated_at: 2026-09-15T00:30:06.351Z
---
Bind one generic cache entry to a stable GitHub repository ID without changing generic source identity. Normalize and validate HostedRepository/v1, retrieval metadata, a sync manifest, and an atomic current pointer through the hosted-review provider store. Keep raw API responses and credentials out of durable state, retain the prior completed snapshot on failure, and expose the logical repository summary through the plugin route and CLI parity golden.
