---
type: is
id: is-01m6k9n12tp6bdycm4qeawtmz0
title: Clarify fresh GitHub dependencies and CLI alias terminology
kind: bug
status: closed
priority: 3
version: 2
labels: []
dependencies: []
parent_id: is-01m6jhctf78vq1v7ndv43jzssy
created_at: 2026-11-04T12:48:26.713Z
updated_at: 2026-11-04T17:21:01.560Z
closed_at: 2026-11-04T17:21:01.560Z
close_reason: "All 17 accepted documentation findings corrected in reviewed/merged PR #298 and independently verified on its exact final-main tree. Completed against actual final main https://github.com/jlevy/metabrowser/commit/db52ec09cf839269da3a56fd396e44f3092995a9; final independent integration review and all nine main CI jobs passed. Original evidence retains its execution pins; genuine future and release scope remains separate."
resolution: null
duplicate_of: null
---
Fresh postlanding documentation review D2: README says all GitHub data reading needs gh, although cached metadata reads do no provider work and remain available without gh. State the dependency on fetching fresh GitHub data. README and installation also call the metabrowser package-name alias a compatibility command; use alias consistently. Update these operator documents in the reviewed documentation follow-up, preserve standard installation behavior, and independently verify the exact successor before closing.
