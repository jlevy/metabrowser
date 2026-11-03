---
type: is
id: is-01m6f3n89kn7ztmfhrzswxnsgz
title: "Review pull requests well on large repositories: fresh mirror and existing checkout"
kind: epic
status: open
priority: 1
version: 31
labels:
  - release:v0.12.0
dependencies: []
child_order_hints:
  - is-01m6f3n8s7enn9mcye32ks6jrd
  - is-01m6f3n9efn9sj7gkavbthag1c
  - is-01m6f3na4z8cvkyyrn5ge794es
  - is-01m6f3nakaknkwvc7j976xxqcg
  - is-01m6f3nb10jmwg0ej1tbf3vdnz
  - is-01m6f3nbfcsnzgmn95f1gr0dsj
  - is-01m6f3nbz5f5rbwbjcs64vj4g2
  - is-01m6f3ncftw4g837wvn9ygqbbx
  - is-01m6f3ncz8hk3e49ernay4yv8x
  - is-01m6f3nddgbv150407xewcjwds
  - is-01m6f3ndv0s9tpwhvbjwdmtkev
  - is-01m6f3ne8f25m4n06r3d09zw9d
  - is-01m6f3neny40jwz0qeanc3avfh
  - is-01m6f3nf55rm1sjpaagqaph6nr
  - is-01m6f3nj5vpvkbw0m300dcy3jr
  - is-01m6f3njzx91ssw9yq9x2smtv5
  - is-01m6f3nkg482640stjteqx3fvw
  - is-01m6f3nm5xr0xc912vqyky74hz
  - is-01m6f3nmnmmceb1c0rgwvdg8as
  - is-01m6f55s2rxqn1fc5gntccjv9g
  - is-01m6f55tgdfq5q1a28hvqzsbrh
  - is-01m6f55vkpt8e119z7c1wdzxat
  - is-01m6f55wr4c9e7h3q7dt8dtex3
  - is-01m6f60ncbgnmwgg9g07wcsj4t
  - is-01m6f60pqc21gnqnct2pdq16zb
  - is-01m6fa9eepyhrcwa35bmbdmjde
  - is-01m6fczffs8pdsdktnahd1ked2
  - is-01m6fvg6hjg91hmegfq5m3sg4b
  - is-01m6g4n54pv6gbm7yzjxbskegg
created_at: 2026-11-02T21:46:44.914Z
updated_at: 2026-11-03T07:23:24.693Z
---
The owner's goal, 2026-11-02: review PRs seamlessly both fresh from the cached mirror and from an existing checkout without duplicating its storage, responsive on large PRs faster than GitHub itself, following the design system rigorously, with all workflows documented cleanly. Found by testing on a real 1.2 GB private repository with a shallow checkout and 211 linked worktrees. All work lands on branch claude/v012-pr-review-workflows, above release stack 278. The Pulls tab itself is a separate stack in the linked session: mb-q3jt, mb-x174, mb-zx9q, mb-cbak, mb-r50o, mb-lnkl, mb-iw1v.

## Notes

2026-11-03 status. Stack 278 is 272-277, 280, 284, 283, with the Pulls tab as stack 286 (279, 281, 285, 287, 288) on top of 283. PR 280 (design system, docs, workflows): reviewed, addressed, CI green at 996ea90d. PR 284 (large-PR performance): three review rounds; E1 (the mount's single long task, slower than github.com at 1,031 files) in progress, mb-ivvw. PR 283 (checkout overlay step 1): two review rounds addressed, CI green at e8b7ff3d, verified on the 1.2 GB private repository; a follow-up review of its last fixes is pending (mb-3kju). Open after that: mb-l351 (overlay step 2), mb-jwfx (quiet timings), mb-i9ll (the owner's own pass), mb-8pyc and mb-2g6f (folder differentials on the tagged head).
