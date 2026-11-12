---
type: is
id: is-01m76bf16dr1tzbrmmg5wfpvbs
title: "PR #341 B4: the entitlement checks pass when codesign cannot read the signature"
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
created_at: 2026-11-11T22:25:41.581Z
updated_at: 2026-11-12T00:14:52.974Z
started_at: 2026-11-11T22:42:32.215Z
closed_at: 2026-11-12T00:14:52.973Z
close_reason: "fixed in d953e301 (B4): require_no_entitlements fails closed on an unreadable signature; scripts/test-scripts.sh"
resolution: null
duplicate_of: null
---
Medium. apps/macos/scripts/build-app.sh:64 and check-dmg.sh:77: codesign failure inside the if pipeline reads as no entitlements. Review B4 https://github.com/jlevy/metabrowser/pull/341#pullrequestreview-5866036340.
