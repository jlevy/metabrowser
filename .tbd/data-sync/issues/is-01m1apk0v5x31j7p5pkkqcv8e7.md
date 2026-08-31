---
type: is
id: is-01m1apk0v5x31j7p5pkkqcv8e7
title: "PR #90 P90-02: The POST render golden pins a 400, not the branch it claims"
kind: bug
status: closed
priority: 1
version: 2
labels: []
dependencies: []
parent_id: is-01m1apk016z6h7ms919ekta9z0
created_at: 2026-08-31T01:22:53.412Z
updated_at: 2026-08-31T01:40:12.907Z
closed_at: 2026-08-31T01:40:12.907Z
close_reason: "Fixed on feat/cli-parity-mechanism; see the disposition map on PR #90."
resolution: null
duplicate_of: null
---
shellroot/render.json is built with printf and unescaped \n, so the JSON string carries real control characters and the body is invalid. Verified: JSONDecodeError at line 1 column 71, and the golden records status 400 with error Invalid JSON body while its prose says it reaches a different branch of the handler. The POST transformed-source branch has no coverage anywhere. Fix: escape as \\n in the fixture and re-record.
