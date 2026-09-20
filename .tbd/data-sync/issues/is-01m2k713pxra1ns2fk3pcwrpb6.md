---
type: is
id: is-01m2k713pxra1ns2fk3pcwrpb6
title: "v0.11 repository and hosted-resource stack: land and retarget completed phase PRs"
kind: task
status: in_progress
priority: 1
version: 50
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
  - release:v0.11.0
  - stack:pr125
  - stack:pr134
  - stack:pr136
  - stack:pr140
  - stack:pr139
  - stack:pr217
  - stack:pr216
dependencies:
  - type: blocks
    target: is-01m2zvffb1z2vsseb9d9nqcj6m
parent_id: is-01kzs5m38dz1egphfwf30c8h7n
hold: blocked
hold_until: null
created_at: 2026-09-15T18:59:49.596Z
updated_at: 2026-09-20T16:48:48.403Z
started_at: 2026-09-16T21:24:51.532Z
---
After explicit approval and after every publication bead records a green formal PR, land and retarget the v0.11 stack in dependency order: Phase 0A, 0B.1, 0B.2, 0B.3, 0C.1, 0C.2, shared repository/provider mirror design, Hosted Review 0D, repository Phase 1A, worktree-free acquisition, content-source boundary, immutable Git-tree source, untrusted-content profile, URL open, provider-job and selected-ref foundation, selected branch, provider foundation, direct PR cache, direct PR view, PR index/navigation, and anchors. Retarget each next PR to its landed base, inspect the exact new-base through HEAD diff, resolve only stacking conflicts, rerun make verify, obtain final green CI, and confirm main contains each layer. This is the sole landing owner; it never blocks constructing a later stack layer and never merges without explicit user approval.

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
