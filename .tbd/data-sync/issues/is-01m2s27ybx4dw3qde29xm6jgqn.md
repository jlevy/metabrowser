---
type: is
id: is-01m2s27ybx4dw3qde29xm6jgqn
title: "CLI: --no-serve so acquisition goldens inspect without ASGI"
kind: task
status: in_progress
priority: 1
version: 5
spec_path: docs/project/specs/active/plan-2026-08-28-cli-first-delivery-map.md
delegate: unknown@cursor
labels:
  - release:v0.11.0
dependencies:
  - type: blocks
    target: is-01m1389rewn2mkj8emj3wxwpr7
parent_id: is-01kzsb4jnyd56wy89xmztkmz2m
hold: null
hold_until: null
created_at: 2026-09-18T01:31:37.213Z
updated_at: 2026-09-18T03:06:59.714Z
started_at: 2026-09-18T02:44:30.720Z
---
Add --no-serve so `metab <url>` can acquire and inspect cache state without starting the ASGI server. The CLI-first delivery map (Open Decisions #1) recommends this as the acquisition trigger: side effect of metab <url>, no /api/cache/acquire write route. Goldens (mb-dg00) need acquire + --api /api/cache/* against an isolated METABROWSER_HOME. Land with the acquire CLI wiring in mb-h51g, not as a standalone mode.

## Notes

PR https://github.com/jlevy/metabrowser/pull/146 on cursor/v011-cli-no-serve-bd04 HEAD f08a2845, stacked on #145. All 7 CI checks green (lint, test 3.12/3.13/3.14/3.14t, distribution, stack-integration). Lands --no-serve for classified file://: acquire into METABROWSER_HOME, print slug/store/strategy/revision, no ASGI, no cache paths. file:// --api /api/cache/* acquires then inspects against an empty throwaway root. Serve/walk/show/check-api refuse Git sources without acquiring; https/ssh stay closed. Cache-hit --no-serve reuses the published store. Ordinary local browsing still skips cache.urls. Do not close until review. Next: mb-3639 portable acquire goldens.
