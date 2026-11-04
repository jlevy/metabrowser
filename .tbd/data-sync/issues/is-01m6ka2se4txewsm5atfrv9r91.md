---
type: is
id: is-01m6ka2se4txewsm5atfrv9r91
title: Qualify asset coherence documentation to newly loaded pages
kind: bug
status: open
priority: 3
version: 1
labels: []
dependencies: []
parent_id: is-01m6jhctf78vq1v7ndv43jzssy
created_at: 2026-11-04T12:55:57.635Z
updated_at: 2026-11-04T12:55:57.635Z
---
Expanded documentation review D5: architecture claims an old asset cannot pair with a new route. Uncached HTML and content-addressed assets provide coherent shell/settings/assets for a newly loaded page; JavaScript in an already open tab is not replaced when the local server restarts. Qualify the documented guarantee and state normal reload after a server build replacement. Add no compatibility adapter, cross-version API policy or product change. Independently verify against the server's actual shell/asset response behavior.
