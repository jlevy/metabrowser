---
type: is
id: is-01m2hrcxgbcrrte71dn2abqyxx
title: Catalog read at 300k rows is 3.9x v0.9.1 (663 ms -> 2,575 ms)
kind: bug
status: open
priority: 1
version: 2
labels:
  - performance
dependencies: []
parent_id: is-01m2hs64m7nfagfxyf7b0hxrhr
created_at: 2026-09-15T05:24:53.387Z
updated_at: 2026-09-15T05:38:50.242Z
---
exp-034 priced `/api/catalog` on the settled 300k index at 2,575 ms against v0.9.1's
663 ms, with an unrelated request's worst wait going 475 ms -> 883 ms.

Priced in isolation at 300,000 rows the parts are: 548 ms building the contract records
(170 ms of it re-validating paths the store admitted at discovery), 196 ms sorting, 113
ms hashing a content identity, and 339 ms encoding a 15.9 MB body. Only the filtering
loop yields.

v0.9.1 answered the same request from its own retained `(path, ext)` tuples with no
per-row contract object, no validation, no sort-key encode and no content hash. That
difference is the regression.

exp-035 took the content-hash part (1.51x on that step, byte-identical digest) and
rejected the sort-key part with measurements; see mb-wpqq. The remaining cost is the
per-row contract object and its validation, which is the same structural work as the
delivery path.

Done when: the catalog read at 300k rows is within 1.1x of v0.9.1, measured on a settled
index on a quiet host.
