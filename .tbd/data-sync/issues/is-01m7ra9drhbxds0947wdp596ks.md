---
type: is
id: is-01m7ra9drhbxds0947wdp596ks
title: "Source ref selector: after a successful switch state.switching stays true, so a page restored from the back/forward cache keeps disabled rows"
kind: bug
status: open
priority: 3
version: 2
labels: []
dependencies: []
parent_id: is-01m7wys615s2mfvbc93c9g2pac
created_at: 2026-11-18T21:51:29.033Z
updated_at: 2026-11-20T17:09:29.996Z
---
Review A of jlevy/metabrowser#567, A6 (pre-existing): after a successful switch, source-ref-selector.js leaves state.switching true. A page restored from the bfcache while its own subject is served keeps its rows disabled until a reload. #567 releases that page's held requests (pageshow persisted) but not its selector; resetting switching on a persisted pageshow fixes it, and makes #567's held === mine guard matter.
