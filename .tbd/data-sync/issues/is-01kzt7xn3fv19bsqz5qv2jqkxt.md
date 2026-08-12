---
type: is
id: is-01kzt7xn3fv19bsqz5qv2jqkxt
title: "PR #32 review MB32-R4: preserve in-process route exceptions in logs"
kind: bug
status: closed
priority: 2
version: 3
labels: []
dependencies: []
parent_id: is-01kzt7x3qqb7y2qgpbxhjg3k3x
created_at: 2026-08-12T05:43:00.462Z
updated_at: 2026-08-12T05:56:11.620Z
closed_at: 2026-08-12T05:56:11.619Z
close_reason: "Fixed in c263112: post-response ASGI exceptions are logged at debug level with their tracebacks while the stable 500 response is preserved."
---
PR #32 senior review MB32-R4 (Low). src/metabrowser/cli/check_api.py _InProcessClient.get. Log caught route exceptions before returning a stable 500 result so debug logging preserves the cause.
