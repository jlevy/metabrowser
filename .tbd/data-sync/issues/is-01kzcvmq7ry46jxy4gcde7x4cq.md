---
type: is
id: is-01kzcvmq7ry46jxy4gcde7x4cq
title: "HTML P1: sandbox and harden the /raw response headers"
kind: task
status: open
priority: 1
version: 3
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
updated_at: 2026-08-07T00:58:17.732Z
---
Ship independently of any UI change. Add a shared response-header builder covering all three branches of raw_file (including the gzip passthrough): X-Content-Type-Options: nosniff and Content-Security-Policy: frame-ancestors 'self' on every raw response, plus a CSP sandbox directive for HTML, SVG, and XML media types. Closes the current path where an in-root .html or .svg executes script on the app origin. Regression tests for the gzip branch and for image/svg+xml.
