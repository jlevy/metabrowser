---
type: is
id: is-01m0f031zmre3tjxm8jsxwr1sn
title: "PR #58 review R9: Container depth bound counts total segments not inner depth, duplicated constant"
kind: bug
status: closed
priority: 2
version: 2
labels: []
dependencies: []
parent_id: is-01m0f02zaw865q3swdc9xvmdb9
created_at: 2026-08-20T07:10:11.955Z
updated_at: 2026-08-20T07:35:57.771Z
closed_at: 2026-08-20T07:35:57.771Z
close_reason: "R9 fixed in c0ae341: plugin_api.MAX_CONTAINER_INNER_DEPTH bounds the inner path from the claiming file, one constant both walks"
---
PR #58, review 4979975854, finding R9. Container depth bound counts total segments not inner depth, duplicated constant. server.py:2650, sidekick.py:53; bound inner depth from the cut, share via plugin_api
