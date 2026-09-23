---
type: is
id: is-01m2k713pxra1ns2fk3pcwrpb6
title: "v0.12 repository and hosted-resource stack: coordinate stabilized landing"
kind: task
status: in_progress
priority: 1
version: 53
spec_path: docs/project/specs/active/plan-2026-08-27-github-provider-and-pull-requests.md
refs:
  - kind: other
    url: https://github.com/jlevy/metabrowser/stack/218
    at: 2026-09-19T17:24:56.130Z
  - kind: pr
    url: https://github.com/jlevy/metabrowser/pull/125
    at: 2026-09-19T17:24:56.131Z
  - kind: pr
    url: https://github.com/jlevy/metabrowser/pull/134
    at: 2026-09-19T17:24:56.131Z
  - kind: pr
    url: https://github.com/jlevy/metabrowser/pull/136
    at: 2026-09-19T17:24:56.131Z
  - kind: pr
    url: https://github.com/jlevy/metabrowser/pull/139
    at: 2026-09-19T17:24:56.131Z
  - kind: pr
    url: https://github.com/jlevy/metabrowser/pull/140
    at: 2026-09-19T17:24:56.131Z
  - kind: pr
    url: https://github.com/jlevy/metabrowser/pull/217
    at: 2026-09-19T17:24:56.131Z
  - kind: pr
    url: https://github.com/jlevy/metabrowser/pull/216
    at: 2026-09-19T17:24:56.131Z
delegate: claude-code@spud10.local
labels:
  - stack:pr125
  - stack:pr134
  - stack:pr136
  - stack:pr140
  - stack:pr139
  - stack:pr217
  - stack:pr216
  - release:v0.12.0
dependencies:
  - type: blocks
    target: is-01m2zvffb1z2vsseb9d9nqcj6m
parent_id: is-01kzs5m38dz1egphfwf30c8h7n
hold: blocked
hold_until: null
created_at: 2026-09-15T18:59:49.596Z
updated_at: 2026-09-23T00:25:12.158Z
started_at: 2026-09-16T21:24:51.532Z
---
Coordinate the whole v0.12 repository/GitHub Stack 218, beginning with #125 -> #134 -> #136 -> #139 -> #140 -> #217 -> #216 and extending with alpha-testing, stabilization, and later feature PRs. Keep exact base/head relationships, current per-layer review dispositions and green CI, top integration evidence against current main, and aligned specs/beads. mb-nhky coordinates later Phase 2A-4C publications within this same stack. Hold all layers until the agreed acceptance milestone is stabilized and the user explicitly approves landing; then land and retarget coherently. Do not treat published draft PRs or passing unit/model tests as completed GitHub alpha acceptance.

## Notes

Do not merge. Do not imply landed.

GitHub stack #218: https://github.com/jlevy/metabrowser/stack/218
#125 → #134 (folded #130 #132 #133) → #136 (folded #135) → #139 (folded #138) → #140 → #217 (folds #208 #210) → #216 (folds #156 and #211–#215).

#140 Bugbot Mediums fixed in da73b878; both threads resolved.
#125 is 2 commits behind origin/main (#137 tbd 0.9.0). Internally consistent; do not restack unless asked.
#217 and #216 are drafts. #216 is large (~101 files).

Landing still requires explicit human approval, then bottom-to-top gh stack merge.

2026-09-20: an independent re-review found #217 and #216 not yet landable; stabilization is tracked in mb-gacf. #207 merged; the stack needs a restack onto main.

2026-09-20: scope narrowed by user decision to the current stack #125 → #134 → #136 → #139 → #140 → #217 → #216 plus PR #209, which lands before #217; later phases are owned by mb-nhky.
The nine future-phase review blockers (mb-innz, mb-9aku, mb-k7lc, mb-cpco, mb-bue2, mb-79sz, mb-r596, mb-mx8q, mb-bf94) moved to mb-nhky, which is also blocked by this bead. mb-gacf was added as a blocker here. Remaining open blockers on this bead: mb-hoae, mb-k900, mb-tsdc, mb-d658, mb-gacf.

2026-09-22 reconciliation: v0.11.0 is released; this is the v0.12 stack. Live GitHub Stack 218 has exact chain #125(ed370a4e) -> #134(10990158) -> #136(e0b713b3) -> #139(4e189c9b) -> #140(93f19061) -> #217(4d25dc9a, draft) -> #216(b3c001a9, draft), all seven checks green per layer. User directs future testing, stabilization, and feature PRs to extend the same stack; hold the whole stack for stabilization and explicit landing approval. mb-nhky coordinates later phase publication but no longer means a separate landing batch. Remaining direct review blockers: mb-k900, mb-tsdc, mb-hoae, mb-gacf. HTML trust mb-d658 is closed and on main through #209, with later hardening inherited through #224. Alpha acceptance is docs/project/specs/active/plan-2026-09-22-v012-alpha-testing.md; no merge or release authorized by this audit.
