---
type: is
id: is-01m6k9n12tp6bdycm4qeawtmz0
title: Clarify fresh GitHub dependencies and CLI alias terminology
kind: bug
status: open
priority: 3
version: 1
labels: []
dependencies: []
parent_id: is-01m6jhctf78vq1v7ndv43jzssy
created_at: 2026-11-04T12:48:26.713Z
updated_at: 2026-11-04T12:48:26.713Z
---
Fresh postlanding documentation review D2: README says all GitHub data reading needs gh, although cached metadata reads do no provider work and remain available without gh. State the dependency on fetching fresh GitHub data. README and installation also call the metabrowser package-name alias a compatibility command; use alias consistently. Update these operator documents in the reviewed documentation follow-up, preserve standard installation behavior, and independently verify the exact successor before closing.
