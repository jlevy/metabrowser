---
type: is
id: is-01m7kdda1kyysv08g87fedzpz5
title: "PR #490 A5: the Chrome session needs the exact port it asked for"
kind: bug
status: in_progress
priority: 2
version: 2
delegate: claude-code@spud10.local
labels: []
dependencies: []
parent_id: is-01m7k4tntv9my4ynk41w81g0sj
hold: null
hold_until: null
created_at: 2026-11-17T00:09:49.874Z
updated_at: 2026-11-17T00:09:58.086Z
started_at: 2026-11-17T00:09:58.085Z
---
Low, PR #490 review A (https://github.com/jlevy/metabrowser/pull/490#pullrequestreview-5929928725). tests/dom/files-totals-stable-chrome.mjs waited for a banner with the requested port; metab --port searches upward.
