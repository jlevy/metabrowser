---
type: is
id: is-01m6f3add4akft3c0x2p54f5v2
title: Overlay of the served checkout, acquired when Files changed opens
kind: task
status: closed
priority: 1
version: 5
spec_path: docs/project/specs/active/plan-2026-10-01-github-pulls-tab.md
labels: []
dependencies:
  - type: blocks
    target: is-01m6f3adv181gkevbha1epsyj1
parent_id: is-01m6f3a2f5v5bkym87p85a0wq2
created_at: 2026-11-02T21:40:49.699Z
updated_at: 2026-11-03T20:17:10.230Z
closed_at: 2026-11-03T20:17:10.230Z
close_reason: "Completed by forward commits in the PR-support stack; independent reviews, rechecks and dispositions are published on the owning PRs. Final integration ea771741211193a387c1771e04df29b5a9698100 passed make verify (4712 Python, 9 expected skips, 373 transcripts), 8 public live tests, installed-wheel Chrome (22 actions, 25 unchanged checkout/Git fingerprints), and all 171 CI jobs across 19 current-head runs on 14 PRs. Final clean review: https://github.com/jlevy/metabrowser/pull/288#pullrequestreview-5758664799 . No PR merged."
resolution: null
duplicate_of: null
---
Step 6, as decided 2026-11-02 by plan-2026-11-02-pr-review-mirror-and-checkout.md (Fit with the Pulls Tab Plan; Finding the Checkout, the Served row; its Delivery step 4). Opening a pull request's Files changed on a folder server creates, the first time, an overlay store borrowing the served checkout's objects, through the acquisition --checkout uses, inside the running server; the comparison is served from that store. Nothing is written to the checkout and no Git runs with it as its repository.

## Notes

2026-11-03 acquisition-policy clarification (supersedes the automatic-on-open wording in this bead, preserving its history): the overlay acquisition implementation is complete. Opening Files changed alone does not create or fetch the overlay. The reader must select Fetch changes from the no_store state; that explicit action uses the shared acquisition API with clone fallback disabled for checkout borrowing, and attaches only the cache-side comparison store. Existing healthy stores can be reused. The folder source root/pin and user checkout stay unchanged, and GET/read paths do not start acquisition. Frozen candidate: 2bd58827700e951c3cd7359efd6fd20bfe33f96d. Supporting validation available to the coordinator includes completed independent source reviews, eight public read-only live GitHub tests, 22 Chrome checks and 25 unchanged checkout/common-Git fingerprints. These are supporting results, not a claim that final gates have finished: exact-head make verify is still running, and the normal push and remote CI remain pending. No PR has been merged. Keep this bead open until the coordinator records the final gates; no closure or sync is performed by this note.
