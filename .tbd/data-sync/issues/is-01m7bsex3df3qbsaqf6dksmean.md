---
type: is
id: is-01m7bsex3df3qbsaqf6dksmean
title: "CI: admitted-git 2.43.7 fails to build under GCC 15 (C23 unreachable macro)"
kind: bug
status: open
priority: 1
version: 1
labels: []
dependencies: []
created_at: 2026-11-14T01:06:29.612Z
updated_at: 2026-11-14T01:06:29.612Z
---
2026-11-14 ~00:55Z: admitted-git (2.43.7) fails on every branch and on main (main 6d009fff, run 43538289133). The runner's GCC 15 compiles C23 by default; its <stddef.h> unreachable() macro collides with git 2.43.7's function in reflog.c. The performance session is fixing devtools/build_admitted_git.sh to build with -std=gnu17 (script in the cache key, so both admitted versions rebuild). Open PRs need main merged in after that lands.
