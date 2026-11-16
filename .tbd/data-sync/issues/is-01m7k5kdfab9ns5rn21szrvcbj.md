---
type: is
id: is-01m7k5kdfab9ns5rn21szrvcbj
title: "PR #485 A6: Open beads in the parent plan change the release assets and Q7, and the plan never names them"
kind: bug
status: closed
priority: 2
version: 3
spec_path: docs/project/specs/active/plan-2026-11-16-macos-app-publishing.md
delegate: claude-code@spud10.local
labels: []
dependencies: []
parent_id: is-01m7k1vctj6d370jg7hqdps4hk
hold: null
hold_until: null
created_at: 2026-11-16T21:53:21.385Z
updated_at: 2026-11-16T22:09:56.436Z
started_at: 2026-11-16T21:53:38.019Z
closed_at: 2026-11-16T22:09:56.433Z
close_reason: "Fixed in 83ef69fc3: the ZIP and manifest (mb-5jr9, mb-92d9) are ruled out of 0.1.0 with the asset names in one common.sh function; Q7 notes the ZIP needs the app's own ticket; Q4 points at mb-fl72; mb-63cx's matrix links mb-5fp7."
resolution: null
duplicate_of: null
---
Medium. PLAN:222-223, :449-464, :557-566; plan-2026-11-10-native-macos-app.md:465-475. mb-5jr9 (ZIP and manifest), mb-92d9, mb-fl72 and mb-5fp7 are not named; a ZIP cannot carry a stapled ticket. Fix: reference all four; put the ZIP and manifest in the asset lists or rule them out and keep the asset list in one place; add the ZIP to Q7; point Q4 at mb-fl72 and the matrix at mb-5fp7. Review A (round 1) of PR #485: https://github.com/jlevy/metabrowser/pull/485#pullrequestreview-5928293258
