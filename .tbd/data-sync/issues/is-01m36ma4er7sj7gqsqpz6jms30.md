---
type: is
id: is-01m36ma4er7sj7gqsqpz6jms30
title: "Serve a pin: browser serving of a file:// pin with forced untrusted profile"
kind: task
status: open
priority: 1
version: 2
spec_path: docs/project/specs/active/plan-2026-09-23-v012-thin-mirror.md
labels:
  - release:v0.12.0
dependencies:
  - type: blocks
    target: is-01m36ma4wj1mvqw8rhgw3mqh6s
parent_id: is-01m36k3w9vgwy97c9hcj2sqrs5
created_at: 2026-09-23T07:57:30.967Z
updated_at: 2026-09-23T07:57:31.409Z
---
Delivery step 3 of the thin-mirror plan. Serve an acquired file:// revision in the browser (lift the serve, walk and check-api refusals where appropriate), install the pinned GitRevisionSubject through the server lifecycle with cleanup, force the untrusted profile on URL-opened roots (mb-99ub), supply repository_context, and decide served /raw relative references (mb-g5je). T1 browser subset without network. Independent review, make verify, green CI.
