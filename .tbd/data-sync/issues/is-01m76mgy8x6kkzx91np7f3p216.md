---
type: is
id: is-01m76mgy8x6kkzx91np7f3p216
title: "PR #341 D2: the generated cask still admits macOS 15"
kind: bug
status: closed
priority: 1
version: 2
labels: []
dependencies: []
parent_id: is-01m76mgk23q075j4w3wjjg27a0
created_at: 2026-11-12T01:04:01.307Z
updated_at: 2026-11-12T01:31:25.354Z
closed_at: 2026-11-12T01:31:25.354Z
close_reason: "fixed in 7e0100a6 (pushed, head 358cebd5): template requires :tahoe; write_cask and test-scripts.sh check the cask against LSMinimumSystemVersion. Disposition: https://github.com/jlevy/metabrowser/pull/341#issuecomment-6811709019"
resolution: null
duplicate_of: null
---
Severity Medium. PR #341, review D (https://github.com/jlevy/metabrowser/pull/341#pullrequestreview-5867388071). apps/macos/packaging/metabrowser-app.rb.template:24 declares depends_on macos: ">= :sequoia" while Package.swift:11 targets .macOS(.v26) and Resources/Info.plist:16 sets LSMinimumSystemVersion 26.0; write_cask (scripts/common.sh:145) copies the stale floor. Fix: raise the cask floor to macOS 26 (:tahoe) and check in scripts/test-scripts.sh that generated casks agree with the app's minimum.
