---
type: is
id: is-01m8e9h43g9vn8ask2b4dqhfv2
title: "Give main's Chrome tier a fifth part: four reached the job's 7-minute limit"
kind: chore
status: closed
priority: 1
version: 4
refs:
  - kind: pr
    url: https://github.com/jlevy/metabrowser/pull/918
    at: 2026-11-27T10:41:55.001Z
delegate: claude-code@vm
labels: []
dependencies: []
hold: null
hold_until: null
created_at: 2026-11-27T10:41:30.224Z
updated_at: 2026-11-27T10:58:48.229Z
started_at: 2026-11-27T10:41:31.450Z
closed_at: 2026-11-27T10:58:48.229Z
close_reason: Merged to main as jlevy/metabrowser#918; main's Chrome tier runs five parts by refreshed weights.
resolution: null
duplicate_of: null
---
Main's Chrome shards took up to 409 s (run 45976882655) and a pull request on main's path 426 s (run 45978583219, cancelled) against the job's 420 s, after the tier grew to 90 tests and 1173 s. Refresh devtools/shard_weights.json from main's newest green run and raise CHROME_SHARDS_MAIN to 5 (235 s of tests a part), with the measurement beside the constant (devtools/ci_plan.sh) and in ci.yml's Chrome job comment.
