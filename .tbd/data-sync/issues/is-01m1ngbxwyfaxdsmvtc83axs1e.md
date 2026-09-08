---
type: is
id: is-01m1ngbxwyfaxdsmvtc83axs1e
title: indexed_dirs counts the root on main but not on the stack
kind: bug
status: closed
priority: 2
version: 2
labels: []
dependencies: []
parent_id: is-01m1mv8fds3d80zj3qmg1cct9b
created_at: 2026-09-04T06:05:48.318Z
updated_at: 2026-09-08T00:02:48.644Z
closed_at: 2026-09-08T00:02:48.641Z
close_reason: Provider diagnostics now count the served root, matching main and progress totals. Regression and the index metadata golden are updated.
resolution: null
duplicate_of: null
---
/api/index/meta reports indexed_dirs=1105 on main and 1104 on the stack for the same 60,000-file corpus, while indexed_files is 60000 on both. The walked trees are identical: extracting every dir path from 'metab --walk --format json' on both builds gives 1,104 paths and an empty diff, so no entry is missing. The difference is that main's counter includes the served root and the refactored IndexProgress.directories_observed does not.

Wire-visible on /api/index/meta, so it is a behaviour change that should be either restored or stated. It also blocks build-against-build comparison: explorations/performance-loop/scan_bench.py now refuses to report when two builds index different entry counts, and this off-by-one trips that guard on every main-vs-stack run.

Found by that guard, which is what it was added for.
