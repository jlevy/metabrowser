---
type: is
id: is-01kzcvmqfy6gw5h36vs1hx3bms
title: "HTML P2: capability set, --untrusted profile, and client publication"
kind: task
status: open
priority: 1
version: 3
spec_path: docs/project/specs/active/plan-2026-08-06-html-rendering-and-trust-model.md
labels: []
dependencies:
  - type: blocks
    target: is-01kzcvmr0d1eyegyds8zpbffbz
parent_id: is-01kzcvm6cpe5b8sb9b9n3gb16g
created_at: 2026-08-07T00:58:17.469Z
updated_at: 2026-08-07T01:47:17.636Z
---
Resolve an immutable capability object before app construction. Add --no-active-content / METAB_ACTIVE_CONTENT=0 and the --untrusted / METAB_UNTRUSTED=1 profile, with individual flags overriding the profile. Publish through client_settings_dict() as CAPABILITIES and via GET /api/capabilities. When active_content is off, drop allow-scripts from the raw sandbox directive (NOT a text/plain downgrade — that reintroduces the type enumeration the unconditional header removed and breaks innocent styled pages). Document the flags in SECURITY.md and the README warning block in the same change. Generalizes the mechanism the file-actions plan defines for mutations rather than adding a parallel one.
