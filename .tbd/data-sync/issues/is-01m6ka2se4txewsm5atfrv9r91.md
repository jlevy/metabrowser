---
type: is
id: is-01m6ka2se4txewsm5atfrv9r91
title: Qualify asset coherence documentation to newly loaded pages
kind: bug
status: closed
priority: 3
version: 2
labels: []
dependencies: []
parent_id: is-01m6jhctf78vq1v7ndv43jzssy
created_at: 2026-11-04T12:55:57.635Z
updated_at: 2026-11-04T17:21:01.576Z
closed_at: 2026-11-04T17:21:01.576Z
close_reason: "All 17 accepted documentation findings corrected in reviewed/merged PR #298 and independently verified on its exact final-main tree. Completed against actual final main https://github.com/jlevy/metabrowser/commit/db52ec09cf839269da3a56fd396e44f3092995a9; final independent integration review and all nine main CI jobs passed. Original evidence retains its execution pins; genuine future and release scope remains separate."
resolution: null
duplicate_of: null
---
Expanded documentation review D5: architecture claims an old asset cannot pair with a new route. Uncached HTML and content-addressed assets provide coherent shell/settings/assets for a newly loaded page; JavaScript in an already open tab is not replaced when the local server restarts. Qualify the documented guarantee and state normal reload after a server build replacement. Add no compatibility adapter, cross-version API policy or product change. Independently verify against the server's actual shell/asset response behavior.
