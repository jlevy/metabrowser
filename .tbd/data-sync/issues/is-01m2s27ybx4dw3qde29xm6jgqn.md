---
type: is
id: is-01m2s27ybx4dw3qde29xm6jgqn
title: "CLI: --no-serve so acquisition goldens inspect without ASGI"
kind: task
status: open
priority: 1
version: 1
spec_path: docs/project/specs/active/plan-2026-08-28-cli-first-delivery-map.md
labels:
  - release:v0.11.0
dependencies: []
parent_id: is-01kzsb4jnyd56wy89xmztkmz2m
created_at: 2026-09-18T01:31:37.213Z
updated_at: 2026-09-18T01:31:37.213Z
---
Add --no-serve so `metab <url>` can acquire and inspect cache state without starting the ASGI server. The CLI-first delivery map (Open Decisions #1) recommends this as the acquisition trigger: side effect of metab <url>, no /api/cache/acquire write route. Goldens (mb-dg00) need acquire + --api /api/cache/* against an isolated METABROWSER_HOME. Land with the acquire CLI wiring in mb-h51g, not as a standalone mode.
