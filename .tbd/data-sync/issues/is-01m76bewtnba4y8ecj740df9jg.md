---
type: is
id: is-01m76bewtnba4y8ecj740df9jg
title: "PR #341 A1/B1/C1: download Replace deletes the original before the download succeeds"
kind: bug
status: closed
priority: 0
version: 3
delegate: claude-code@spud10.local
labels: []
dependencies: []
parent_id: is-01m76bebqayw0ze5xz60yhthtw
hold: null
hold_until: null
created_at: 2026-11-11T22:25:37.107Z
updated_at: 2026-11-12T00:14:48.902Z
started_at: 2026-11-11T22:28:52.504Z
closed_at: 2026-11-12T00:14:48.892Z
close_reason: "fixed in 499430e1 (A1/B1/C1): staged replacement via StagedDownload/DownloadCoordinator; DownloadTests with real WKDownload; tests hardened in 19911565"
resolution: null
duplicate_of: null
---
Blocker in A, B, C. apps/macos/Sources/Metabrowser/BrowserWindowController.swift:341 removes the destination before WKDownload writes it; a failed transfer loses the original. Reviews: A1 https://github.com/jlevy/metabrowser/pull/341#pullrequestreview-5866036012, B1 https://github.com/jlevy/metabrowser/pull/341#pullrequestreview-5866036340, C1 https://github.com/jlevy/metabrowser/pull/341#pullrequestreview-5866036572.
