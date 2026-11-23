---
type: is
id: is-01m82s7mc3zy6r5wyfd43pyjch
title: "PR #709 A2: 5 s asks re-arm the poll, so the 30 s poll never fires and a dead server is never reported"
kind: bug
status: closed
priority: 2
version: 2
spec_path: docs/project/specs/active/plan-2026-11-22-pull-request-update-cadence.md
labels: []
dependencies: []
parent_id: is-01m82s73za15hfvfw96fdn9e19
created_at: 2026-11-22T23:25:03.222Z
updated_at: 2026-11-22T23:45:08.310Z
closed_at: 2026-11-22T23:45:08.292Z
close_reason: "fixed in aebc9cbb9: automatic asks re-arm the poll only when they started a refresh or the poll should be fast; failed automatic asks are reported; page-session steps fail on 53ded9dbc"
resolution: null
duplicate_of: null
---
High. pull-page.js askForRefresh -> scheduleNext. Reproduced in K (36 POSTs, 1 GET in 180 s). https://github.com/jlevy/metabrowser/pull/709#pullrequestreview-6015073163 ; evidence https://github.com/jlevy/metabrowser/pull/709#pullrequestreview-6015081008
