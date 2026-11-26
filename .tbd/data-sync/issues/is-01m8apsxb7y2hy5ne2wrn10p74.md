---
type: is
id: is-01m8apsxb7y2hy5ne2wrn10p74
title: KPress stylesheets load one after another on a cold open (~360 ms chain)
kind: task
status: open
priority: 3
version: 1
labels: []
dependencies: []
created_at: 2026-11-26T01:16:31.974Z
updated_at: 2026-11-26T01:16:31.974Z
---
Observed while measuring PR #859: on a cold open, KPress's stylesheets load serially, a ~360 ms chain before rendered Markdown can paint. Measure the chain and load them in parallel or preload them, per the asset loading tiers.
