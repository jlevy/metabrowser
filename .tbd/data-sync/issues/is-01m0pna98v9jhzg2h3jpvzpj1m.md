---
type: is
id: is-01m0pna98v9jhzg2h3jpvzpj1m
title: Carried a correct poll key from one endpoint to another where it means nothing
kind: bug
status: closed
priority: 1
version: 3
labels: []
dependencies: []
parent_id: is-01m0pn7vkfkd7tfzt7r331jkp8
created_at: 2026-08-23T06:35:49.906Z
updated_at: 2026-08-23T07:24:18.776Z
---
CORRECTED after checking the repository rather than assuming. The first version of this bead said the poll key was misspelled and implied bench_serving.py had the same flaw. It does not, and the real mistake is more instructive.

WHAT ACTUALLY HAPPENED. `index_status` is a REAL field -- on `/api/rollup`, where devtools/bench_serving.py polls it correctly at line 579. It does not exist on `/api/tree`, which publishes `tally_cache_status`. The comparison harness carried a correct field name across from one endpoint to another, where it silently meant nothing.

So this is not a typo. It is the same class of error as its sibling mb-hr8o: a fact that is true of one endpoint applied to a different one, in a route family whose payloads look alike. That is the pattern worth guarding, and it will not be caught by spelling care.

WHY IT COST TWO ROUNDS. `dict.get` on an absent key returns None, the comparison is False, and the poll waits. Every run consumed its full 420-second deadline and reported no timing. A run that sits for seven minutes and returns nothing reads as a build that is slow to index -- which is exactly the thing being measured, so the broken harness was indistinguishable from the result it existed to detect.

Note bench_serving.py degrades better here by design: it reports `converged: false` and `timed_out_at_s`, so a poll that never matches is visible as a non-result rather than as a slow one.

THE FIX, now in devtools/compare_builds.py: assert the poll key is present in the FIRST response and fail immediately naming the key and listing what the payload does contain. One request separates a wrong key from a slow scan; a deadline does not.

## Notes

FIXED in #73, devtools/compare_builds.py. The poll key is asserted against the FIRST response: if it is absent the harness fails immediately, naming the key and listing what the payload does contain, rather than waiting out its deadline. One request separates a wrong key from a slow scan.
