---
type: is
id: is-01m8dez0t2axanhgmch18ngx5z
title: "test_recording_is_what_a_served_mirror_answers (pulls readiness): fetched_at/checked_at recorded 20 s apart once in CI"
kind: bug
status: open
priority: 2
version: 2
labels: []
dependencies: []
created_at: 2026-11-27T02:57:14.050Z
updated_at: 2026-11-27T03:01:22.837Z
---
CI on https://github.com/jlevy/metabrowser/pull/912 at 60d62bbe (run 45930955850, unit 3.13 4/4, job 140283302128): tests/test_github_pulls_readiness_session.py::test_recording_is_what_a_served_mirror_answers failed check_recording, its fixture github-pulls-readiness-responses.json differing at one answer: 'fetched_at' 12:01:10Z recorded, 12:00:50Z actual, 'checked_at' null recorded, 12:01:10Z actual, and the probe's 'at' 12:01:10Z vs 12:00:50Z. So in that run the list's fetch and its later check landed on different steps of the session's clock than the recording expects, as if a background read or the probe ran on the other side of a clock step. The PR touched no server or github plugin Python since its previous head (0d1decc8), where the same test passed, as it did on main 9d99df3e; it passed 6/6 locally at 60d62bbe. Find which step's timing the recording depends on and make the session wait for it, rather than re-recording.

## Notes

The job's one re-run (run 45930955850, attempt 2) passed, and ci-ok with it.
