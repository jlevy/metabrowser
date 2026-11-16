---
type: is
id: is-01m7jj4mrcjr4wm3cchsmsebs8
title: "PR #476 A2: Cold mount of an unlabelled pull request moves the tab bar up 26 px when its record lands"
kind: bug
status: closed
priority: 2
version: 3
delegate: claude-code@spud10
labels: []
dependencies: []
parent_id: is-01m7jgg4b9taqwxcfevgd9c6gc
hold: null
hold_until: null
created_at: 2026-11-16T16:13:14.379Z
updated_at: 2026-11-16T17:10:05.185Z
started_at: 2026-11-16T16:13:20.954Z
closed_at: 2026-11-16T17:10:05.184Z
close_reason: "Fixed in de4118672 (coordinator's option 1): a cold mount holds the header and tab column for --loading-state-delay by opacity (.github-pull-cold), lifted by the first header with a record; a record that lands in the quiet period while the header waits for the held first paint stays unseen until that paint (.github-pull-cold-held). Measured in place in headless Chrome 152 (5/30/120/600 ms, labelled and unlabelled), recorded beside the rule; new cold-landing header Chrome part (44 checks) fails at eafcfab and passes after; coldHold browserless session pins the state."
resolution: null
duplicate_of: null
---
Severity: Medium. PR #476 Review A (round 1), finding A2: https://github.com/jlevy/metabrowser/pull/476#pullrequestreview-5923174293. References: pull-page.js:4719-4725, :4733-4748; server.py:1674-1682.
