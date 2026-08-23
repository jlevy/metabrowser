---
type: is
id: is-01m0pna98v9jhzg2h3jpvzpj1m
title: Bench harness polled a status field the server never publishes
kind: bug
status: open
priority: 1
version: 1
labels: []
dependencies: []
parent_id: is-01m0pn7vkfkd7tfzt7r331jkp8
created_at: 2026-08-23T06:35:49.906Z
updated_at: 2026-08-23T06:35:49.906Z
---
WHAT HAPPENED. The comparison harness waited for the scan to settle by polling `/api/tree` for `index_status == "done"`. The server publishes no such field; it publishes `tally_cache_status`. The condition was therefore never true, every run ran to its 420-second deadline, and the harness reported no `index_done` timing at all.

WHY IT WAS EXPENSIVE. It did not look like a bug. A run that sits for seven minutes and returns nothing reads as a build that is slow to index -- which is precisely the thing under measurement, so the broken harness was indistinguishable from the result it was supposed to detect. It cost two full comparison rounds before the field name was checked against the server.

THE GENERAL SHAPE, which is what makes this worth filing rather than just fixing: a poll loop on a misspelled key cannot fail. `dict.get` returns None, the comparison is False, and the loop waits. Every wrong key degrades silently into a timeout.

THE FIX. A poll must assert that the key it waits on exists in the first response, and fail immediately if it does not. One request is enough to tell a typo from a slow scan, and the failure then names the key instead of consuming the deadline. The same applies to `summarise()` in the comparison script, which still reads `index_status` from the payload -- harmless there, since a missing key is simply omitted, but it is the same stale name and it should go.
