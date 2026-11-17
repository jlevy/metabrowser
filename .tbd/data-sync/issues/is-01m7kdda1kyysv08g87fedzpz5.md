---
type: is
id: is-01m7kdda1kyysv08g87fedzpz5
title: "PR #490 A5: the Chrome session needs the exact port it asked for"
kind: bug
status: closed
priority: 2
version: 3
delegate: claude-code@spud10.local
labels: []
dependencies: []
parent_id: is-01m7k4tntv9my4ynk41w81g0sj
hold: null
hold_until: null
created_at: 2026-11-17T00:09:49.874Z
updated_at: 2026-11-17T02:33:14.160Z
started_at: 2026-11-17T00:09:58.085Z
closed_at: 2026-11-17T02:33:14.159Z
close_reason: "fixed on PR #490 at 0855877 (CI run 43992596826 green); disposition: https://github.com/jlevy/metabrowser/pull/490#issuecomment-6936212072"
resolution: null
duplicate_of: null
---
Low, PR #490 review A (https://github.com/jlevy/metabrowser/pull/490#pullrequestreview-5929928725). tests/dom/files-totals-stable-chrome.mjs waited for a banner with the requested port; metab --port searches upward.
