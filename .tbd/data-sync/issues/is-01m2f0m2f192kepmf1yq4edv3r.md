---
type: is
id: is-01m2f0m2f192kepmf1yq4edv3r
title: "PR #115 review R5: mb-afdb notes and PR body item numbers do not match the bead list"
kind: bug
status: closed
priority: 2
version: 2
labels: []
dependencies: []
parent_id: is-01m2f0m0sdxg3fe8v091zxkby8
created_at: 2026-09-14T03:50:53.152Z
updated_at: 2026-09-14T04:48:11.141Z
closed_at: 2026-09-14T04:48:11.140Z
close_reason: "Fixed: PR #115 body and mb-afdb notes renumbered to the bead list (done 1, 2, 4, 8, 9; remaining 3, 5, 6, 7); notes rewritten in full keeping the first-rows paragraph"
resolution: null
duplicate_of: null
---
PR #115 review R5 (Low). Bead mb-afdb notes and the PR #115 body.

Item numbers from 5 on do not match mb-afdb's own numbered list (4 = probe-server nonce plus file lock, 5 = report annotation plus shared identity check, 6 = compare_builds attestation, 7 = A/A mode, 8 = dirty, 9 = README). Notes say "fixes 1, 2, 4, 5, and 9 ... 3, 6, 7, and 8 remain", which reads as report annotation done and dirty open, the reverse of the truth.

Fix: renumber both to the list: done = 1, 2, 4, 8, 9; remaining = 3, 5, 6, 7. Rewrite mb-afdb notes in full (update --notes-file replaces), preserving the first-rows paragraph.
