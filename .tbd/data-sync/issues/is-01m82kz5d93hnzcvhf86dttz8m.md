---
type: is
id: is-01m82kz5d93hnzcvhf86dttz8m
title: Remove byte sizes from PR navigation while preserving overview and Diff summary
kind: bug
status: closed
priority: 2
version: 4
refs:
  - kind: pr
    url: https://github.com/jlevy/metabrowser/pull/708
    at: 2026-11-22T22:37:02.218Z
delegate: codex@spud10
labels: []
dependencies: []
parent_id: is-01m7hgpc9550w78kmwqsvv64xh
hold: null
hold_until: null
created_at: 2026-11-22T21:53:02.885Z
updated_at: 2026-11-23T00:16:20.991Z
started_at: 2026-11-22T21:54:35.478Z
closed_at: 2026-11-23T00:16:20.954Z
close_reason: "Independently reviewed and merged in Metabrowser #708 at 5c4afed47 after its exact hosted run and current main CI passed. Confirmed in the active Mac development preview."
resolution: null
duplicate_of: null
---
PR Overview keeps the shared blue byte unit style and size-based emphasis from #695. Remove compressed/raw byte amounts from navigation rows. Preserve PR navigation line-change counts and the Diff summary with file statuses and its totals. Verify with the same data in overview and in the nav.
