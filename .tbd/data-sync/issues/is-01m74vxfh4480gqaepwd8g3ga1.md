---
type: is
id: is-01m74vxfh4480gqaepwd8g3ga1
title: "PR #347 C2: after a lost CAS, open_pull_request can pin a head this store never fetched"
kind: bug
status: closed
priority: 2
version: 2
labels: []
dependencies: []
parent_id: is-01m74vwmegp0f11eb7vj9pnq0t
created_at: 2026-11-11T08:34:43.363Z
updated_at: 2026-11-11T09:41:57.602Z
closed_at: 2026-11-11T09:41:57.601Z
close_reason: "fixed in ecdaaa51: open_pull_request checks has_commit on the winner and falls back to the cached record; R9 test"
resolution: null
duplicate_of: null
---
Severity: Medium. PR #347 review C round 1 at 8dd80d0c (https://github.com/jlevy/metabrowser/pull/347#pullrequestreview-5855769655). References: pulls.py:1125, :1130, pull_record.py:518-519.
