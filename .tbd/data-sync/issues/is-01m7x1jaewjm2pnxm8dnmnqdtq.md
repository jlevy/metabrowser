---
type: is
id: is-01m7x1jaewjm2pnxm8dnmnqdtq
title: "Cache layout and contract: repos/ and sources/ with short readable names, one vocabulary, a stated deletion guarantee, sizes and pruning"
kind: epic
status: in_progress
priority: 1
version: 15
spec_path: docs/project/specs/active/plan-2026-08-11-open-repo-from-git-url.md
refs:
  - kind: pr
    url: https://github.com/jlevy/metabrowser/pull/551
    at: 2026-11-20T19:14:55.644Z
  - kind: pr
    url: https://github.com/jlevy/metabrowser/pull/647
    at: 2026-11-20T19:14:55.645Z
  - kind: pr
    url: https://github.com/jlevy/metabrowser/pull/666
    at: 2026-11-20T19:14:55.645Z
labels:
  - Improvement
dependencies: []
parent_id: is-01kzs5m38dz1egphfwf30c8h7n
child_order_hints:
  - is-01m7wxxan4v3hedteasg82q02s
  - is-01m7x1f1scztk0y814r77bz58v
  - is-01m7vrbkq0241m0fr2fmkgx1ej
  - is-01m7m9v3mwpg9rgacw38xp0376
  - is-01m7x8aemh8m150e3806ct28rf
  - is-01m7x8afdch1746ake734g9r60
  - is-01m7x8ag6z4efv8z79hajaa1ak
created_at: 2026-11-20T17:55:15.547Z
updated_at: 2026-11-25T03:57:41.111Z
extensions:
  linear:
    id: 1910be4b-70e6-4d39-ad72-341b9d3c22ce
    linked_at: 2026-11-20T19:16:56.532Z
---
Owner decisions 2026-11-20 on attic/cache-layout-research/report.txt: repos/ (rename from repository-stores/) and source slugs respelled with single dashes and base36 digests in one f03 step (mb-dwq7); recents move to the state directory and the deletion guarantee is 'whenever no metab is running' (mb-pml0); later, removal and pruning on the open-repo plan's store lease.
