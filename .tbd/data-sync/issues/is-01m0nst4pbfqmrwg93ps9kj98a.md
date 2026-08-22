---
type: is
id: is-01m0nst4pbfqmrwg93ps9kj98a
title: "File header: truncate the root prefix at the start, not the end"
kind: feature
status: open
priority: 2
version: 1
labels: []
dependencies: []
parent_id: is-01m0ndp6h7a3hx27zbswtknk89
created_at: 2026-08-22T22:35:09.387Z
updated_at: 2026-08-22T22:35:09.387Z
---
The served-root prefix truncates at its END, so a narrow pane keeps the least useful part of the path and drops the part nearest what you are looking at. `/Users/someone/wrk/github/projectname` clips to `/Users/someone/wrk/git…`.

Requested: truncate at the BEGINNING with a leading ellipsis, so the trailing part of the path is always the part that survives -- `…/wrk/github/projectname`.

Note the interaction with mb-fos4: the prefix is the first thing to give up width and reaches zero before the crumbs narrow, so this changes what is legible over the whole range between a full root and none of it.

Implementation note: `direction: rtl` is the usual CSS route to a leading ellipsis, but it reorders neutral characters -- a path's leading `/` or `~` can jump to the far end. Whatever is used has to be checked in a real browser against a path with leading punctuation, not assumed.
