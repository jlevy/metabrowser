---
type: is
id: is-01m7tv7gz4yk6tygqfexgtw0s2
title: Tabular data browsing and live SQLite
kind: epic
status: in_progress
priority: 2
version: 22
spec_path: docs/project/specs/active/plan-2026-11-19-tabular-data-and-live-sqlite.md
refs:
  - kind: pr
    url: https://github.com/jlevy/metabrowser/pull/617
    at: 2026-11-20T19:14:56.794Z
  - kind: pr
    url: https://github.com/jlevy/metabrowser/pull/649
    at: 2026-11-20T19:14:56.795Z
  - kind: pr
    url: https://github.com/jlevy/metabrowser/pull/656
    at: 2026-11-20T19:14:56.795Z
  - kind: pr
    url: https://github.com/jlevy/metabrowser/pull/668
    at: 2026-11-20T19:14:56.795Z
labels:
  - linear
  - Feature
dependencies: []
child_order_hints:
  - is-01m7tv7hddd6gkc23q2592jdad
  - is-01m7tv7hwjzejd9eyeebhep0f8
  - is-01m7tv7jb1aytm2d0dydd2yec7
  - is-01m7v772tf23nxy3z35v5dts42
  - is-01m7v77386t1ch9w7s3n7b7w2z
  - is-01m7vtcztdy0sy8dj632sffkgv
  - is-01m7vtd09bppvgqam5h87zpnvh
  - is-01m7vtd156nbtfkn13rdtvm7yq
  - is-01m7vtd1yhvcp2szqx4m266c1p
  - is-01m7vtd2rax4r1pfqnb3q8f11v
  - is-01m7vtd3gzexvj5w72h4gbemj5
  - is-01m7vtd4bjh7f8rsg0z9jqy9w6
  - is-01m7vtd571483vj430fqd5tw4y
  - is-01m7v9mwy0ye52geq4eqdxwz5a
created_at: 2026-11-19T21:26:01.444Z
updated_at: 2026-11-20T19:15:51.928Z
extensions:
  linear:
    id: da4dab2f-0682-4c31-8c9a-29da1bda661e
    linked_at: 2026-11-20T18:01:45.674Z
---
Generic table plugin (UI, query model, source protocol) with source plugins for CSV/TSV, record lists, and SQLite; nondestructive live SQLite reads; live reload for open files. See the spec.

## Notes

2026-11-20 audit: Plan merged (#617); the owner adopted each key decision's recommendation on 2026-11-20 (mb-nv9k), and Decision 12 can be revisited before Phase 7. Stack PRs #649 (Phase 1, declared plugin dependencies) and #656 (Phase 2, table protocol and CSV/TSV) are open drafts; Phases 3 to 8 have no PR yet. mb-cggp (SQLite POSIX locks) was added.
