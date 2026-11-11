---
type: is
id: is-01m76bf16dr1tzbrmmg5wfpvbs
title: "PR #341 B4: the entitlement checks pass when codesign cannot read the signature"
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
created_at: 2026-11-11T22:25:41.581Z
updated_at: 2026-11-11T22:42:32.216Z
started_at: 2026-11-11T22:42:32.215Z
---
Medium. apps/macos/scripts/build-app.sh:64 and check-dmg.sh:77: codesign failure inside the if pipeline reads as no entitlements. Review B4 https://github.com/jlevy/metabrowser/pull/341#pullrequestreview-5866036340.
