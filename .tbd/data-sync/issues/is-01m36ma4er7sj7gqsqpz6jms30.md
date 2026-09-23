---
type: is
id: is-01m36ma4er7sj7gqsqpz6jms30
title: "Serve a pin: browser serving of a file:// pin with forced untrusted profile"
kind: task
status: closed
priority: 1
version: 3
spec_path: docs/project/specs/active/plan-2026-09-23-v012-thin-mirror.md
labels:
  - release:v0.12.0
dependencies:
  - type: blocks
    target: is-01m36ma4wj1mvqw8rhgw3mqh6s
parent_id: is-01m36k3w9vgwy97c9hcj2sqrs5
created_at: 2026-09-23T07:57:30.967Z
updated_at: 2026-09-23T17:39:14.290Z
closed_at: 2026-09-23T17:39:14.281Z
close_reason: "Serve a pin: PR #229 (codex/v012-serve-pin, head cad7dba9, above Simplify #228). A file:// pin is served in the browser, opened in the app lifespan with a fresh generation per start, forced untrusted, with /api/cache/* and /raw/<path> refused beside a pin and an isolation sweep over all routes. --check-api runs on a pin, and GET /api/source/status and a revision label are added. Independent review found no P0 or P1; its P2 and P3s are fixed. make test: 3187 passed and 192 goldens. CI green on all nine checks."
resolution: null
duplicate_of: null
---
Delivery step 3 of the thin-mirror plan. Serve an acquired file:// revision in the browser (lift the serve, walk and check-api refusals where appropriate), install the pinned GitRevisionSubject through the server lifecycle with cleanup, force the untrusted profile on URL-opened roots (mb-99ub), supply repository_context, and decide served /raw relative references (mb-g5je). T1 browser subset without network. Independent review, make verify, green CI.
