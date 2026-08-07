---
type: is
id: is-01kzcvm6cpe5b8sb9b9n3gb16g
title: HTML rendering and an explicit content-trust model
kind: epic
status: open
priority: 1
version: 6
spec_path: docs/project/specs/active/plan-2026-08-06-html-rendering-and-trust-model.md
labels:
  - security
dependencies: []
parent_id: is-01kxnx985gd2k5epmcswersqdk
child_order_hints:
  - is-01kzcvmq7ry46jxy4gcde7x4cq
  - is-01kzcvmqfy6gw5h36vs1hx3bms
  - is-01kzcvmqr515dr7afbvc0e6krq
  - is-01kzcvmr0d1eyegyds8zpbffbz
created_at: 2026-08-07T00:57:59.957Z
updated_at: 2026-08-07T01:47:27.167Z
---
Render full-page static HTML in an opaque-origin sandbox, and introduce the explicit trust model that makes it safe by default. Governing invariant: content viewed through Metabrowser gets exactly the privilege a browser would give the same file opened directly (file:// parity), and never Metabrowser's server-side API. Also closes two existing holes: /raw executes in-root HTML/SVG on the app origin, and /api accepts cross-site fire-and-forget requests (POST /api/kpress/export writes under the root today). SECURITY.md 'Content Trust Model' section documents current truth; the spec owns the deltas. See the spec for design and phasing.
