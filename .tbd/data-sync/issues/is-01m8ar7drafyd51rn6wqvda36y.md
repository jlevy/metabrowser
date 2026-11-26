---
type: is
id: is-01m8ar7drafyd51rn6wqvda36y
title: "PR #861 A4: size line sums per-layer sizes beside the combined file count"
kind: bug
status: open
priority: 2
version: 1
labels: []
dependencies: []
parent_id: is-01m8ar6wz990fewz7m05yjp9yk
created_at: 2026-11-26T01:41:23.335Z
updated_at: 2026-11-26T01:41:23.335Z
---
Medium. pull_stack.py:946-966, stackSizeInput. Coordinator: measure the combined diff once where the comparison is built, read with kept_change_size; if too costly, measure and leave bytes out. Review: https://github.com/jlevy/metabrowser/pull/861#pullrequestreview-6067404346
