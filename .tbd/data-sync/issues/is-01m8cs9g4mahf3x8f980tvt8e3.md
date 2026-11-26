---
type: is
id: is-01m8cs9g4mahf3x8f980tvt8e3
title: Improve measured post-load navigation and provider fetch bottlenecks
kind: task
status: in_progress
priority: 1
version: 5
spec_path: docs/project/specs/active/plan-2026-11-26-post-load-performance.md
refs:
  - kind: pr
    url: https://github.com/jlevy/metabrowser/pull/894
    at: 2026-11-26T21:19:42.905Z
delegate: codex@spud10.local
labels: []
dependencies: []
parent_id: is-01m8cs8jdw8yh0hvdy6449jm9j
hold: null
hold_until: null
created_at: 2026-11-26T20:38:28.747Z
updated_at: 2026-11-26T21:19:42.910Z
started_at: 2026-11-26T20:55:40.744Z
---
Highest-priority diagnostic: on the fresh Pulls journey, a checkout-store Git fetch began before the click and ended 15.1 s after it. The selected PR job's first gh account check began 0.28 s after that, and the description appeared around 18.3 s after click. Catalog refresh accounted for half of overlapping gh spans. Test whether a selected description read can publish while Git acquisition is in flight, without invalidating account, generation, or cache ownership. Then test startup history preparation and prefetch priority. Initial image continuity fix and headless preparation and HTTP probes are committed. Judged timing and native WKWebView remain.
