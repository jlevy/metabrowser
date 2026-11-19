---
type: is
id: is-01m7tg7y76e86bgjcdfh02cvg0
title: Pulls reveal's reach bound overcounts where issues share the number sequence
kind: task
status: open
priority: 3
version: 1
labels: []
dependencies: []
created_at: 2026-11-19T18:14:00.677Z
updated_at: 2026-11-19T18:14:00.677Z
---
From review B on #611 (B-L1): placeSought's reach, newest - number < displayLimit, counts issue numbers as newer pull requests, so in an issue-heavy repository a stack walk can bounce between Open and Closed instead of staying on All (design-system.md, Navigation Reveals the Item). Fix: have the pulls route return an exact count of newer rows (COUNT(*) WHERE number > ?), or use All's held rows when All has been read.
