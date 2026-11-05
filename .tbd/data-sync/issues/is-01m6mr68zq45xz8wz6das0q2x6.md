---
type: is
id: is-01m6mr68zq45xz8wz6das0q2x6
title: Test whether missing PR details dominate first-click latency
kind: task
status: in_progress
priority: 1
version: 2
spec_path: docs/project/specs/active/plan-2026-08-21-load-time-performance.md
delegate: codex-prefetch
labels: []
dependencies: []
parent_id: is-01m6mp811vf52jmazawykb3bw6
hold: null
hold_until: null
created_at: 2026-11-05T02:21:46.358Z
updated_at: 2026-11-05T02:21:46.973Z
started_at: 2026-11-05T02:21:46.972Z
---
Test the missing-detail case before changing prefetch. On unchanged db52, the catalog is lightweight GraphQL metadata and omits body; a complete PR refresh first reads core and then five parallel conversation/check branches before account recheck and publication. Hover reads cached records only. A held catalog therefore need not mean a first-selected PR has a held detailed record. Measure the same public PR with absent versus held core records, keeping Git objects, starting view, assets and browser-origin states explicit; do not infer an improvement from different PR sizes. Primary metric: trusted click to correct header and useful description; keep rich Markdown and remaining conversation readiness separate. Record provider request count/bytes, first-core and final-publication timestamps, queueing, cancellation and account/source ownership. Only then evaluate bounded preparation of existing full records or honest progressive core publication. Do not present empty comments/checks as complete or fetch all conversations merely because summaries exist. Initial diagnostic subject is public jlevy/metabrowser PR294, whose core is confirmed absent while the 286-row catalog is held. Parent mb-4ifm; H77, reserved exp-045.
