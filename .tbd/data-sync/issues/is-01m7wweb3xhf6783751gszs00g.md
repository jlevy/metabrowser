---
type: is
id: is-01m7wweb3xhf6783751gszs00g
title: test_github_ref_pulls timed the publisher's fsyncs against the busy timeout instead of proving the scan holds no transaction
kind: bug
status: closed
priority: 3
version: 5
labels: []
dependencies: []
parent_id: is-01m2gb3gpn7vcsw0as4xa243tg
created_at: 2026-11-20T16:25:42.268Z
updated_at: 2026-11-20T18:53:33.655Z
closed_at: 2026-11-20T18:53:33.654Z
close_reason: "Fixed by #660 (merged 7fdcf0afd): the test holds the scan with Events instead of timing the publisher's fsyncs."
resolution: null
duplicate_of: null
---
PR 655 run 44771960710 job 136411653812 (admitted-git 2.43.7): assert time.monotonic() - began < 0.25 failed at 0.35 s. A wall-clock bound this tight fails on a loaded runner; unrelated to the change under test. Rerun once; consider a bound that does not depend on runner load.
