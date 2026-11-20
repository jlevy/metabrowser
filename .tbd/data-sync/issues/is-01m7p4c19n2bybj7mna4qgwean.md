---
type: is
id: is-01m7p4c19n2bybj7mna4qgwean
title: "Merge-ready: fdu-swap groundwork stack on the Python provider (switchover deferred to next release)"
kind: epic
status: in_progress
priority: 1
version: 12
spec_path: docs/project/specs/active/plan-2026-08-23-inventory-provider-refactor-and-fdu-adoption.md
delegate: claude-code@vm
labels: []
dependencies: []
parent_id: is-01m0r8xt95921dabcddjjm7csf
child_order_hints:
  - is-01m7p4c2tjmjska4ch21ved6rn
  - is-01m7p4c3r2wk28pqee4jfvch9m
  - is-01m7p4c4k114cvzxn6dafmpebm
  - is-01m7p4c5cbth29aj909fszft6g
  - is-01m7p4c682mk4m7s54ek2fke31
  - is-01m7p4c75cerj8mx3jyseranfe
  - is-01m7p4c811xftze81vrvjrp91h
  - is-01m7p4c8tzny1f6r62xncw0t2e
  - is-01m7p4c9paycffpk124cwhr189
hold: null
hold_until: null
created_at: 2026-11-18T01:29:34.261Z
updated_at: 2026-11-20T17:15:49.362Z
started_at: 2026-11-18T01:29:34.982Z
---
User request 2026-11-18: 'make sure everything is ready to merge incrementally ... the parts that are possible to merge incrementally with no real operational change (cleanups and refactors with the pure Python backend), and then make the switchover something we could delay for the next release.' Mode: merge-ready (review-and-merge-prs). The nine stack PRs (#498, #501, #502, #503, #507, #508, #518, #519, #520) add no fdu provider, flag, or extra; the switchover (mb-urh5 thin adapter + experimental flag + extra, mb-e9uw macOS preference, and any default change) stays out of this release.

## Notes

2026-11-20 audit: All nine stack PRs (#498, #501, #502, #503, #507, #508, #518, #519, #520) are still open drafts, so their beads stay in progress. Nothing here is done until they merge.
