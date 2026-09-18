---
type: is
id: is-01kzcvmq7ry46jxy4gcde7x4cq
title: "HTML P1: sandbox /raw responses and require same-origin proof on /api"
kind: task
status: in_progress
priority: 1
version: 10
spec_path: docs/project/specs/active/plan-2026-08-06-html-rendering-and-trust-model.md
delegate: unknown@cursor
labels:
  - security
  - release:v0.11.0
dependencies:
  - type: blocks
    target: is-01kzcvmqfy6gw5h36vs1hx3bms
  - type: blocks
    target: is-01kzcvmqr515dr7afbvc0e6krq
  - type: blocks
    target: is-01m2pn3sm2980e2bjnfd3b4xvp
parent_id: is-01kzcvm6cpe5b8sb9b9n3gb16g
hold: null
hold_until: null
created_at: 2026-08-07T00:58:17.207Z
updated_at: 2026-09-18T04:09:50.990Z
started_at: 2026-09-18T04:04:15.120Z
extensions:
  linear:
    id: aa27e880-f003-4490-80ca-7e9c75b72c12
    linked_at: 2026-08-16T08:05:43.348Z
---
Ship independently of any UI change; both halves of the content/API boundary land together. (1) Shared response-header builder on all three raw_file branches (incl. gzip passthrough): unconditional 'Content-Security-Policy: sandbox allow-scripts allow-popups allow-forms allow-downloads' plus 'X-Content-Type-Options: nosniff' on every raw response — no script-capable type list, and deliberately NO frame-ancestors (it would break nested iframes/framesets in previewed pages, since the opaque-origin ancestor never matches 'self'). (2) Same-origin proof on /api/* in _HostValidationMiddleware: accept Sec-Fetch-Site: same-origin or a matching Origin; reject Origin: null and foreign origins; keep no-header requests (curl) working. State-changing routes require the application/json Content-Type header explicitly — request.json() ignores the header today, so POST /api/kpress/export (which WRITES under the root) is cross-site CSRF-able right now. (3) Regression tests: gzip branch, .svg, nested-frame loading, cross-origin /api rejection matrix. (4) Rewrite the SECURITY.md not-yet-enforced list into enforced guarantees.

## Notes

From the layer review: /api/cache/* (mb-k54c) are the first /api routes returning state from outside the served root. raw_file used to serve browsed files same-origin with no CSP, so an HTML file inside any browsed root could fetch those routes. This PR closes both halves on the default branch (not stacked on the unmerged cache PRs): unconditional CSP sandbox+nosniff on every raw_file branch, same-origin proof plus JSON Content-Type on /api in _HostValidationMiddleware. /raw stays reachable as a content surface. Tests: tests/test_content_trust.py and tests/test_raw_passthrough.py. SECURITY.md rewritten to enforced guarantees. Branch: cursor/v011-html-raw-sandbox-bd04. Bead stays open for review; do not merge until CI is green.
