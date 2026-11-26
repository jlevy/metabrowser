---
type: is
id: is-01m8ar70h5n8kaday1fw6bbrkv
title: "PR #861 A1: label-less stack opened cold keeps an empty labels row"
kind: bug
status: open
priority: 1
version: 1
labels: []
dependencies: []
parent_id: is-01m8ar6wz990fewz7m05yjp9yk
created_at: 2026-11-26T01:41:09.787Z
updated_at: 2026-11-26T01:41:09.787Z
---
High. stack-page.js:1305-1315, 1907-1912. Coordinator: decide the labels row at first paint from PullListRow.labels via the Pulls list rows; remove the empty row when the answer lands with none; drop held-once-seen; pin a cold stack with no labels in the mount session. Review: https://github.com/jlevy/metabrowser/pull/861#pullrequestreview-6067404346
