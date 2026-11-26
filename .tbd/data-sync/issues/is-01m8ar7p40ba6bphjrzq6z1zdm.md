---
type: is
id: is-01m8ar7p40ba6bphjrzq6z1zdm
title: "PR #861 A6: members row not held from first paint for an unknown stack"
kind: bug
status: open
priority: 3
version: 1
labels: []
dependencies: []
parent_id: is-01m8ar6wz990fewz7m05yjp9yk
created_at: 2026-11-26T01:41:31.896Z
updated_at: 2026-11-26T01:41:31.896Z
---
Low. stack-page.js:1318. Coordinator: hold the members row at first paint even when the Pulls tab does not know the stack. Review: https://github.com/jlevy/metabrowser/pull/861#pullrequestreview-6067404346
