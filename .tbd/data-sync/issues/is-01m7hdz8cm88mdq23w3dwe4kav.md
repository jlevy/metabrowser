---
type: is
id: is-01m7hdz8cm88mdq23w3dwe4kav
title: "PR #464 A2: Quick Search for the pull request shown reveals nothing after the Pulls tab's button"
kind: bug
status: in_progress
priority: 2
version: 2
delegate: claude-code@spud10
labels: []
dependencies: []
parent_id: is-01m7hcjm7dvfsqanbt2jtdyxfy
hold: null
hold_until: null
created_at: 2026-11-16T05:41:09.140Z
updated_at: 2026-11-16T05:41:16.431Z
started_at: 2026-11-16T05:41:16.430Z
---
Medium. Review A on PR #464 (https://github.com/jlevy/metabrowser/pull/464#pullrequestreview-5915452177). pulls-nav.js:262-277 preserveScroll carried state drops reveal; main-tabs.js:356; pulls-panel.js:2878-2886. An explicit reveal must end a kept scroll.
