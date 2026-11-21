---
type: is
id: is-01m7zxyjvts8tm1hhm8s7ny9kr
title: Verify simulated quarantine without requiring Finder agent display metadata
kind: bug
status: closed
priority: 2
version: 4
refs:
  - kind: pr
    url: https://github.com/jlevy/metabrowser/pull/690
    at: 2026-11-21T21:06:51.002Z
delegate: codex@spud10
labels: []
dependencies: []
parent_id: is-01m7hgpc9550w78kmwqsvv64xh
hold: null
hold_until: null
created_at: 2026-11-21T20:49:46.361Z
updated_at: 2026-11-21T21:37:52.790Z
started_at: 2026-11-21T21:06:00.632Z
closed_at: 2026-11-21T21:37:52.789Z
close_reason: Merged as jlevy/metabrowser#690 after real macOS red-green verification, an independent review, and both exact PR workflows.
resolution: null
duplicate_of: null
---
On the build Mac with the external scratch volume, Foundation successfully quarantines a file and returns simulated then already, but macOS can leave the optional agent display field empty. The portable release mock succeeds and the launch verifier does not use the agent field for acceptance. Keep the test strict about persistent and unchanged quarantine across both helper calls without requiring the optional diagnostic label.
