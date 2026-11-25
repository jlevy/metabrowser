---
type: is
id: is-01m898qq8ztfnphwfhqm61dst3
title: "PR #838 A3: nothing runs the stack page Guided Review mount"
kind: bug
status: open
priority: 2
version: 1
labels: []
dependencies: []
parent_id: is-01m898q9z40pe69kyfzr97xxjv
created_at: 2026-11-25T11:51:25.726Z
updated_at: 2026-11-25T11:51:25.726Z
---
Medium. paintGuided (stack-page.js:1102-1202) and the guided branch of paintBody (1208-1271) run in no browserless session or Chrome check. Fix: a session mounting mountStackPage with a stub SDK on recorded answers, and a parity row. Review: https://github.com/jlevy/metabrowser/pull/838#pullrequestreview-6057040965
