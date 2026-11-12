---
type: is
id: is-01m76beytfnh61fka05rjyrf19
title: "PR #341 A6/C5: universal releases write a cask for the arm64 artifact"
kind: bug
status: closed
priority: 2
version: 3
delegate: claude-code@spud10.local
labels: []
dependencies: []
parent_id: is-01m76bebqayw0ze5xz60yhthtw
hold: null
hold_until: null
created_at: 2026-11-11T22:25:39.150Z
updated_at: 2026-11-12T00:14:50.770Z
started_at: 2026-11-11T22:42:32.578Z
closed_at: 2026-11-12T00:14:50.769Z
close_reason: "fixed in 943dbcd4 (A6/C5): write_cask fills the image's architecture and checks URL and checksum; scripts/test-scripts.sh and a universal rehearsal"
resolution: null
duplicate_of: null
---
Medium. apps/macos/scripts/release.sh:68 and packaging/metabrowser-app.rb.template:10: the cask URL always names -arm64.dmg while the checksum is of the built (possibly universal) image. Reviews: A6 https://github.com/jlevy/metabrowser/pull/341#pullrequestreview-5866036012, C5 https://github.com/jlevy/metabrowser/pull/341#pullrequestreview-5866036572.
