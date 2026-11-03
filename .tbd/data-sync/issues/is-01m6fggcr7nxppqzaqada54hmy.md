---
type: is
id: is-01m6fggcr7nxppqzaqada54hmy
title: "PR #284 A14: gzip in accept-encoding matches gzip;q=0"
kind: bug
status: closed
priority: 1
version: 2
labels: []
dependencies: []
parent_id: is-01m6fgg7mr3vtzcxz7m1njv3ck
created_at: 2026-11-03T01:31:17.126Z
updated_at: 2026-11-03T02:31:06.103Z
closed_at: 2026-11-03T02:31:06.103Z
close_reason: "A14 rebutted: Starlette's GZipMiddleware compresses gzip;q=0 after the route regardless; a q-value parse would only recompress on the loop. test_the_routes_gzip_test_is_the_middlewares pins it."
resolution: canceled
duplicate_of: null
---
Low suggestion. Review A https://github.com/jlevy/metabrowser/pull/284#pullrequestreview-5745572379. diff/sidekick.py:231-243. Same as Qodo inline comment 3 https://github.com/jlevy/metabrowser/pull/284#discussion_r4449451257
