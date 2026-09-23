---
type: is
id: is-01m2k713pxra1ns2fk3pcwrpb6
title: "v0.12 repository and hosted-resource stack: coordinate stabilized landing"
kind: task
status: in_progress
priority: 1
version: 56
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
dependencies: []
parent_id: is-01kzs5m38dz1egphfwf30c8h7n
hold: blocked
hold_until: null
created_at: 2026-09-15T18:59:49.596Z
updated_at: 2026-09-23T00:58:00.750Z
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

2026-09-22 dependency reconciliation: removed the obsolete edge making mb-nhky wait for mb-n2ro (an early landing). mb-n2ro now waits for mb-nhky, mb-gnr9 and mb-eegt as well as its existing publication/review gates. Later feature publication can proceed on the unmerged stack, while final whole-stack landing remains held until the planned publications, alpha acceptance, review and explicit approval. This reverses the superseded split-landing sequence; it closes no product work.

2026-09-22 completed review/publication: https://github.com/jlevy/metabrowser/pull/225 is the ready-for-review eighth layer of Stack 218, head ff94e3676bf0f7caab7a8bdfdbb18eb8b1f8e1c9 over #216 b3c001a96eed64eb77961c2b7165b103af98b77c. The original seven heads and exact chain are unchanged. All seven CI checks passed: https://github.com/jlevy/metabrowser/actions/runs/35803858717 . Local make verify passed (3112 pytest tests, two skips, 147 CLI transcript checks, dependency audits and installed-wheel/distribution checks); pre-push gate passed. Real unmodified Git 2.50.1 CLI T0 smoke passed for cold/warm acquisition, nested Markdown/JSON/tree/progress, origin-absent reuse, and local filesystem inspection. Independent Astra plan review found no actionable plan blocker: https://github.com/jlevy/metabrowser/pull/225#issuecomment-5787107670 . Full top-level review: https://github.com/jlevy/metabrowser/pull/216#issuecomment-5786877244 . #136/#139 later functional deltas received independent technical review; #217/#216 acceptance remains open. New finding mb-sumg and future installed/browser acceptance mb-gnr9 remain open. Specs, QA procedure, roadmap, active release labels, PR descriptions and dependency graph are reconciled. mb-xada historical handoff is closed; #219/mb-dbue remain open awaiting a released tbd replacement. All future work extends Stack 218 and the whole stack stays held for stabilization and explicit landing approval. No GitHub URL/PR end-to-end pass, merge or release is claimed.
