---
type: is
id: is-01m6f3a2f5v5bkym87p85a0wq2
title: "Step 6: Files changed on a checkout, from an overlay of the served checkout"
kind: feature
status: closed
priority: 1
version: 10
spec_path: docs/project/specs/active/plan-2026-10-01-github-pulls-tab.md
labels: []
dependencies: []
parent_id: is-01m6f39t9zax1nbajkkasya6st
child_order_hints:
  - is-01m6f3add4akft3c0x2p54f5v2
  - is-01m6f3adv181gkevbha1epsyj1
created_at: 2026-11-02T21:40:38.500Z
updated_at: 2026-11-03T20:17:10.221Z
closed_at: 2026-11-03T20:17:10.221Z
close_reason: "Completed by forward commits in the PR-support stack; independent reviews, rechecks and dispositions are published on the owning PRs. Final integration ea771741211193a387c1771e04df29b5a9698100 passed make verify (4712 Python, 9 expected skips, 373 transcripts), 8 public live tests, installed-wheel Chrome (22 actions, 25 unchanged checkout/Git fingerprints), and all 171 CI jobs across 19 current-head runs on 14 PRs. Final clean review: https://github.com/jlevy/metabrowser/pull/288#pullrequestreview-5758664799 . No PR merged."
resolution: null
duplicate_of: null
---
Delivery step 6. When the base and head commits are in the checkout, the page shows the diff with read-only Git and names the base it used. When they are missing, it says so, writes nothing, and gives the two commands.

## Notes

2026-11-03 HANDOFF (paused for another agent): not started. Starts after step 5, from the overlay acquisition in the stack below (plan-2026-11-02-pr-review-mirror-and-checkout.md).

2026-11-03 status: the plan's step 6 is revised (483b3a17): Files changed on a checkout reads an overlay store borrowing the served checkout's objects, created when the reader opens Files changed, per plan-2026-11-02-pr-review-mirror-and-checkout.md. Not started; it follows step 5. Children mb-5bqy and mb-awvw are rewritten to match.

2026-11-02: gate updated, reported by the other session: the owner accepted the overlay store design, taking every recommendation. Plan: docs/project/specs/active/plan-2026-11-02-pr-review-mirror-and-checkout.md on claude/v012-pr-review-design at b330e0c9; read its Fit with the Pulls Tab Plan and Finding the Checkout sections before designing this step. It assumes: no-loss is relaxed for overlays; only a checkout named with --checkout or served with metab <checkout> may lend, so a metab <checkout> server opening a pull request is a legitimate lender with zero flags; an uncertain merge base deepens as a bounded job and reads base_uncertain meanwhile and offline; an existing full mirror is kept and the conversion printed; borrows sits beside location in status and the heading tooltip. Do not start until the other session says its overlay step 1 on claude/v012-overlay-acquisition is reviewed. That plan's step 4 rewrites the Pulls plan's step 5 text.

2026-11-02: GATE. Same as mb-cbak: wait for the owner's decision on the overlay store proposal before fixing this step's design.

2026-11-03 completion clarification (supersedes the not-started step-6 status, preserving its history): checkout Files changed is implemented through the same store comparison service used by managed repository URLs. A healthy existing store can be reused. Opening Files changed does not automatically acquire or fetch; a no_store page offers the explicit Fetch changes action, which acquires an overlay borrowing the served checkout without writing the checkout or silently falling back to a full clone. Explicit Files Refresh can repair observed failures for the displayed immutable comparison; metadata updates do not silently move the displayed head. Typed unavailable states and documented recovery limits remain intentional. Frozen candidate: 2bd58827700e951c3cd7359efd6fd20bfe33f96d. Supporting validation available to the coordinator includes completed independent source reviews, eight public read-only live GitHub tests, 22 Chrome checks and 25 unchanged checkout/common-Git fingerprints. These are supporting results, not a claim that final gates have finished: exact-head make verify is still running, and the normal push and remote CI remain pending. No PR has been merged. Keep this bead open until the coordinator records the final gates; no closure or sync is performed by this note.
