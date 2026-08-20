---
type: is
id: is-01m0f031zmre3tjxm8jsxwr1sn
title: "PR #58 review R9: Container depth bound counts total segments not inner depth, duplicated constant"
kind: bug
status: open
priority: 2
version: 1
labels: []
dependencies: []
parent_id: is-01m0f02zaw865q3swdc9xvmdb9
created_at: 2026-08-20T07:10:11.955Z
updated_at: 2026-08-20T07:10:11.955Z
---
PR #58, review 4979975854, finding R9. Container depth bound counts total segments not inner depth, duplicated constant. server.py:2650, sidekick.py:53; bound inner depth from the cut, share via plugin_api
