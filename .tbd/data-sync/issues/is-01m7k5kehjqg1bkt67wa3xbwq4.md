---
type: is
id: is-01m7k5kehjqg1bkt67wa3xbwq4
title: "PR #485 A8: The notary-log reader has no rule for a log that could not be fetched"
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
created_at: 2026-11-16T21:53:22.481Z
updated_at: 2026-11-16T22:09:57.783Z
started_at: 2026-11-16T21:53:38.794Z
closed_at: 2026-11-16T22:09:57.781Z
close_reason: "Fixed in 83ef69fc3: mb-tfap retries the log fetch and makes a missing or unparsable log fatal under NOTARIZE=1, with both fixtures."
resolution: null
duplicate_of: null
---
Low. PLAN:445-448; apps/macos/scripts/notarize.sh:75. Fix: retry the fetch; under NOTARIZE=1 a missing or unparsable log is fatal; add that case to the fixtures. Review A (round 1) of PR #485: https://github.com/jlevy/metabrowser/pull/485#pullrequestreview-5928293258
