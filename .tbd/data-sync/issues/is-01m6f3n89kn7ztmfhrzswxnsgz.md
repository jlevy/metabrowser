---
type: is
id: is-01m6f3n89kn7ztmfhrzswxnsgz
title: "Review pull requests well on large repositories: fresh mirror and existing checkout"
kind: epic
status: open
priority: 1
version: 29
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
created_at: 2026-11-02T21:46:44.914Z
updated_at: 2026-11-03T04:43:25.104Z
---
The owner's goal, 2026-11-02: review PRs seamlessly both fresh from the cached mirror and from an existing checkout without duplicating its storage, responsive on large PRs faster than GitHub itself, following the design system rigorously, with all workflows documented cleanly. Found by testing on a real 1.2 GB private repository with a shallow checkout and 211 linked worktrees. All work lands on branch claude/v012-pr-review-workflows, above release stack 278. The Pulls tab itself is a separate stack in the linked session: mb-q3jt, mb-x174, mb-zx9q, mb-cbak, mb-r50o, mb-lnkl, mb-iw1v.
