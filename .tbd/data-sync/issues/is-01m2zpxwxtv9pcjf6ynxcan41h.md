---
type: is
id: is-01m2zpxwxtv9pcjf6ynxcan41h
title: "BEADS-1: apply the bead bookkeeping corrections and fix the mb-n2ro landing graph and inverted dependency edges"
kind: chore
status: closed
priority: 2
version: 5
spec_path: docs/project/specs/active/plan-2026-08-11-open-repo-from-git-url.md
labels:
  - release:v0.11.0
  - stack:pr216
dependencies: []
parent_id: is-01m2yxd3tnr1s2zf0h0jat1ey2
created_at: 2026-09-20T15:28:34.743Z
updated_at: 2026-09-20T16:51:38.181Z
closed_at: 2026-09-20T16:51:38.180Z
close_reason: Bookkeeping corrections applied and synced; mb-n2ro blocker set split into mb-nhky (later phases) per user decision; inverted and vestigial dependency edges fixed; seven owner beads created (mb-pkho, mb-rati, mb-e32d, mb-d1za, mb-bi2c, mb-dbue, mb-nhky).
resolution: null
duplicate_of: null
---
Finding BEADS-1 from the v0.11 stabilization review. Owning layer: PR #216. Full evidence, path:line, and suggested fix are in the notes of mb-gacf under BEADS-1.

## Notes

Decision 2026-09-20 (user): split the mb-n2ro blocker set so the current seven-PR stack (#125 to #216) plus #209 can land without the Phase 2A to 4C publication beads. Bookkeeping corrections are being applied by an agent first; the split is applied after it finishes to avoid concurrent writes to mb-n2ro.

Applied 2026-09-20 by the bookkeeping agent (all PR facts re-verified with gh on 2026-09-20):

Closed: mb-r1f3, mb-5mrx, mb-vsze (PR 125/134/136 coverage stubs; coverage comments
pull/125#issuecomment-5748280103, pull/134#issuecomment-5748280197,
pull/136#issuecomment-5748280295; mb-r1f3's architecture reconciliation reassigned to
mb-k2m1). mb-dznr (tbd #304 merged 2026-09-16, metabrowser #137 merged 2026-09-17).
mb-wgm8 (remainder is mb-hgus, confirmed open).

Status in_progress -> open, each with a dated note: mb-kicj, mb-fbm2, mb-30ox, mb-1qsn,
mb-vknc.

Notes corrected (appended, never overwritten): mb-dxmb (#141 CLOSED, #208 CLOSED, grammar
now rides #217), mb-k900 (head b09c01e0 -> 70091d81; mb-gacf), mb-z335 and mb-hoae (edge
tests exist in tests/test_git_revision_content_routes.py and tests/test_git_tree_source.py;
#216 remainder in mb-gacf), mb-fn3h, mb-w6oa (pushed, CI green, both Bugbot threads
resolved), mb-f44p, mb-1ss2, mb-gzl3 (pushed, CI green), mb-rldx (superseded line
prepended), mb-6m25 (route is /api/cache/source/{slug}, routes.py:80), mb-xada
(heads, #316 and #207 merged), mb-n2ro.

Labels: mb-n2ro -stack:pr132/133/135/141/142/146/147/148, +stack:pr139/pr217/pr216;
mb-bf94 +stack:publication.

Dependency edges: added mb-ew38 blocked by mb-d658; removed mb-r19i blocked by mb-2f7r
(closed, superseded architecture); removed mb-lnkl and mb-bue2 blocked by mb-79sz (spec
orders Phase 3C at line 1173 before Phase 4A at line 1187 in
docs/project/specs/active/plan-2026-08-27-github-provider-and-pull-requests.md); removed
mb-k900 blocked by mb-dxmb (mb-dxmb closes when mb-k900 closes).

mb-n2ro split (user-approved 2026-09-20): created mb-nhky "v0.11 later phases: land and
retarget Phase 2A to 4C PRs" (P1, parent mb-k7zy, release:v0.11.0, hold blocked), blocked
by mb-innz, mb-9aku, mb-k7lc, mb-cpco, mb-bue2, mb-79sz, mb-r596, mb-mx8q, mb-bf94 and
mb-n2ro; removed those nine from mb-n2ro; added mb-gacf as a blocker of mb-n2ro. mb-n2ro
now blocks mb-nhky and is blocked by mb-hoae, mb-k900, mb-tsdc, mb-d658, mb-gacf plus the
closed historical ones.

New beads for unowned Phase 1B-a work (spec
docs/project/specs/active/plan-2026-08-11-open-repo-from-git-url.md, Phase 1B-a at line
1774), all release:v0.11.0: mb-pkho (parent mb-z335), mb-rati, mb-e32d, mb-d1za (parent
mb-h51g), mb-bi2c and mb-dbue (parent mb-k7zy, mb-dbue P3).
