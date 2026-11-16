---
type: is
id: is-01m7k5kfgwtr16yhe2w1cjyj1x
title: "PR #485 A10: The release workflow validates the tag only after approval, in the job that holds the secrets"
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
created_at: 2026-11-16T21:53:23.483Z
updated_at: 2026-11-16T22:09:59.300Z
started_at: 2026-11-16T21:53:39.545Z
closed_at: 2026-11-16T22:09:59.299Z
close_reason: "Fixed in 83ef69fc3: a check job with no environment and contents: read validates the tag, VERSION and main ancestry and ends the run when the release already has assets; sign needs check; concurrency grouped by the tag's ref with cancel-in-progress: false."
resolution: null
duplicate_of: null
---
Low. PLAN:329-343, :482-487. Fix: a check job with no environment and contents: read that validates tag, VERSION and main ancestry and ends the run when the release already has assets; sign needs check; concurrency per ref with cancel-in-progress: false. Review A (round 1) of PR #485: https://github.com/jlevy/metabrowser/pull/485#pullrequestreview-5928293258
