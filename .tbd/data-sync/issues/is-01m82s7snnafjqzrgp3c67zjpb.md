---
type: is
id: is-01m82s7snnafjqzrgp3c67zjpb
title: "PR #709 A4: server probe floor equals the page period, so jitter drops asks"
kind: bug
status: closed
priority: 2
version: 2
spec_path: docs/project/specs/active/plan-2026-11-22-pull-request-update-cadence.md
labels: []
dependencies: []
parent_id: is-01m82s73za15hfvfw96fdn9e19
created_at: 2026-11-22T23:25:08.652Z
updated_at: 2026-11-22T23:45:12.763Z
closed_at: 2026-11-22T23:45:12.740Z
close_reason: "fixed in aebc9cbb9: PROBE_FLOOR_S 4 s below the page's 5 s; freshness test pins an ask at +5 s minus 2 ms"
resolution: null
duplicate_of: null
---
Medium. served_pull.py probe_due vs ATTENDED_PROBE_S. https://github.com/jlevy/metabrowser/pull/709#pullrequestreview-6015073163
