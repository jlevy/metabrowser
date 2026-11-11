---
type: is
id: is-01m76beytfnh61fka05rjyrf19
title: "PR #341 A6/C5: universal releases write a cask for the arm64 artifact"
kind: bug
status: in_progress
priority: 2
version: 2
delegate: claude-code@spud10.local
labels: []
dependencies: []
parent_id: is-01m76bebqayw0ze5xz60yhthtw
hold: null
hold_until: null
created_at: 2026-11-11T22:25:39.150Z
updated_at: 2026-11-11T22:42:32.580Z
started_at: 2026-11-11T22:42:32.578Z
---
Medium. apps/macos/scripts/release.sh:68 and packaging/metabrowser-app.rb.template:10: the cask URL always names -arm64.dmg while the checksum is of the built (possibly universal) image. Reviews: A6 https://github.com/jlevy/metabrowser/pull/341#pullrequestreview-5866036012, C5 https://github.com/jlevy/metabrowser/pull/341#pullrequestreview-5866036572.
