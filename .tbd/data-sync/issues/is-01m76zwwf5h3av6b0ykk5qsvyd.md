---
type: is
id: is-01m76zwwf5h3av6b0ykk5qsvyd
title: "DownloadTests flake: a replacement that fails midway sometimes ends early"
kind: bug
status: open
priority: 2
version: 1
spec_path: docs/project/specs/active/plan-2026-11-10-native-macos-app.md
labels: []
dependencies: []
parent_id: is-01m748xpx7bjg68tfaf3q4nxmj
created_at: 2026-11-12T04:22:47.012Z
updated_at: 2026-11-12T04:22:47.012Z
---
From the #341 CI investigation: DownloadTests.aReplacementThatFailsMidwayKeepsTheOriginal sometimes fails with 'the download ended early: unknown error' (4 times in loaded runs at 807f9a56, 3 of 15 at 862a013a, never in CI). The networking process logs 'parser eof did not terminate full message' right after launch, then Task finished with error -1. Cause unproven; instrument the test server and reproduce.
