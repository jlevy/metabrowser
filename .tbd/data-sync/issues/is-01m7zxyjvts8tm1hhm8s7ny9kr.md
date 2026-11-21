---
type: is
id: is-01m7zxyjvts8tm1hhm8s7ny9kr
title: Verify simulated quarantine without requiring Finder agent display metadata
kind: bug
status: open
priority: 2
version: 1
labels: []
dependencies: []
parent_id: is-01m7hgpc9550w78kmwqsvv64xh
created_at: 2026-11-21T20:49:46.361Z
updated_at: 2026-11-21T20:49:46.361Z
---
On the build Mac with the external scratch volume, Foundation successfully quarantines a file and returns simulated then already, but macOS can leave the optional agent display field empty. The portable release mock succeeds and the launch verifier does not use the agent field for acceptance. Keep the test strict about persistent and unchanged quarantine across both helper calls without requiring the optional diagnostic label.
