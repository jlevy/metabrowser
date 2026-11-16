---
type: is
id: is-01m7hdz8cm88mdq23w3dwe4kav
title: "PR #464 A2: Quick Search for the pull request shown reveals nothing after the Pulls tab's button"
kind: bug
status: closed
priority: 2
version: 3
delegate: claude-code@spud10
labels: []
dependencies: []
parent_id: is-01m7hcjm7dvfsqanbt2jtdyxfy
hold: null
hold_until: null
created_at: 2026-11-16T05:41:09.140Z
updated_at: 2026-11-16T06:28:45.895Z
started_at: 2026-11-16T05:41:16.430Z
closed_at: 2026-11-16T06:28:45.894Z
close_reason: Fixed in 4f55a7e (one-shot again intent; an explicit reveal ends a kept scroll); confirmed by nav-reveal-session.js (tabs and pulls list steps) and test_nav_reveal_chrome.py step 10, which fail at 0b49516.
resolution: null
duplicate_of: null
---
Medium. Review A on PR #464 (https://github.com/jlevy/metabrowser/pull/464#pullrequestreview-5915452177). pulls-nav.js:262-277 preserveScroll carried state drops reveal; main-tabs.js:356; pulls-panel.js:2878-2886. An explicit reveal must end a kept scroll.
