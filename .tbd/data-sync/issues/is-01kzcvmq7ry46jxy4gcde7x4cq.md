---
type: is
id: is-01kzcvmq7ry46jxy4gcde7x4cq
title: "HTML P1: sandbox /raw responses and require same-origin proof on /api"
kind: task
status: open
priority: 1
version: 4
spec_path: docs/project/specs/active/plan-2026-08-06-html-rendering-and-trust-model.md
labels:
  - security
dependencies:
  - type: blocks
    target: is-01kzcvmqfy6gw5h36vs1hx3bms
  - type: blocks
    target: is-01kzcvmqr515dr7afbvc0e6krq
parent_id: is-01kzcvm6cpe5b8sb9b9n3gb16g
created_at: 2026-08-07T00:58:17.207Z
updated_at: 2026-08-07T01:47:11.723Z
---
Ship independently of any UI change; both halves of the content/API boundary land together. (1) Shared response-header builder on all three raw_file branches (incl. gzip passthrough): unconditional 'Content-Security-Policy: sandbox allow-scripts allow-popups allow-forms allow-downloads' plus 'X-Content-Type-Options: nosniff' on every raw response — no script-capable type list, and deliberately NO frame-ancestors (it would break nested iframes/framesets in previewed pages, since the opaque-origin ancestor never matches 'self'). (2) Same-origin proof on /api/* in _HostValidationMiddleware: accept Sec-Fetch-Site: same-origin or a matching Origin; reject Origin: null and foreign origins; keep no-header requests (curl) working. State-changing routes require the application/json Content-Type header explicitly — request.json() ignores the header today, so POST /api/kpress/export (which WRITES under the root) is cross-site CSRF-able right now. (3) Regression tests: gzip branch, .svg, nested-frame loading, cross-origin /api rejection matrix. (4) Rewrite the SECURITY.md not-yet-enforced list into enforced guarantees.
