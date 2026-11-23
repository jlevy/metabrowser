---
type: is
id: is-01m82rnv0jhjgdax26mc4xjc4t
title: Cap macOS recent folder menus at 16 entries
kind: feature
status: closed
priority: 2
version: 4
refs:
  - kind: pr
    url: https://github.com/jlevy/metabrowser/pull/712
    at: 2026-11-22T23:41:15.697Z
delegate: codex@spud10
labels: []
dependencies: []
parent_id: is-01m7hgpc9550w78kmwqsvv64xh
hold: null
hold_until: null
created_at: 2026-11-22T23:15:20.207Z
updated_at: 2026-11-23T00:42:46.197Z
started_at: 2026-11-22T23:17:53.851Z
closed_at: 2026-11-23T00:42:46.197Z
close_reason: "Independently reviewed and merged in #712 at 2eed43d59 after CLI, Swift, general macOS CI, and current main gates passed."
resolution: null
duplicate_of: null
---
Show at most 16 recent targets in the native title-bar folder chooser and File > Open Recent. Keep recency order, existing Home and open-folder entries, and the stored history. Preserve the shared File and Dock menu list policy.
