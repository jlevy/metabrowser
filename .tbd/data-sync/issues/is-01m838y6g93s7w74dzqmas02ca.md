---
type: is
id: is-01m838y6g93s7w74dzqmas02ca
title: Correct the 0.13.0 release notes for plugin SDK 0.8
kind: bug
status: closed
priority: 1
version: 5
refs:
  - kind: pr
    url: https://github.com/jlevy/metabrowser/pull/727
    at: 2026-11-23T03:59:44.694Z
  - kind: other
    url: https://github.com/jlevy/metabrowser/actions/runs/45109953461
    at: 2026-11-23T04:25:14.578Z
delegate: codex@spud10
labels: []
dependencies: []
parent_id: is-01m7hhr3n6wpvfm1zpsxjh210t
hold: null
hold_until: null
created_at: 2026-11-23T03:59:31.268Z
updated_at: 2026-11-23T06:28:43.451Z
started_at: 2026-11-23T03:59:39.771Z
closed_at: 2026-11-23T06:28:43.450Z
close_reason: "The SDK 0.8 migration and strict live-smoke follow-up are included in the reviewed #727 release preparation. Exact isolated make verify, PR CI and final main CI all passed."
resolution: null
duplicate_of: null
---
The draft release body and some folded entries say Plugin SDK 0.7 although the 0.13 runtime and built-in manifests require SDK 0.8. Make the changelog and release notes accurate, explain the plugin compatibility change, and preserve the published 0.12.0 history.
