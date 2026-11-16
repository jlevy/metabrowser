---
type: is
id: is-01m7k5knhyp4wsz8fy1ndc2dj5
title: "PR #485 A21: Commit the G2 intermediate under apps/macos instead of downloading it in the signing job"
kind: bug
status: closed
priority: 3
version: 3
spec_path: docs/project/specs/active/plan-2026-11-16-macos-app-publishing.md
delegate: claude-code@spud10.local
labels: []
dependencies: []
parent_id: is-01m7k1vctj6d370jg7hqdps4hk
hold: null
hold_until: null
created_at: 2026-11-16T21:53:29.661Z
updated_at: 2026-11-16T22:10:05.162Z
started_at: 2026-11-16T21:53:43.811Z
closed_at: 2026-11-16T22:10:05.161Z
close_reason: "Fixed in 83ef69fc3: mb-qu6j commits the G2 intermediate under apps/macos/packaging with its SHA-256 and a SUPPLY-CHAIN-SECURITY.md entry; O1 installs it and mb-3ey5 imports it, so the job downloads nothing."
resolution: null
duplicate_of: null
---
Suggestion. A public certificate; the pin then lives in Git and the job downloads nothing. Review A (round 1) of PR #485: https://github.com/jlevy/metabrowser/pull/485#pullrequestreview-5928293258
