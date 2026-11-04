---
type: is
id: is-01m5wd8d441bkardnt96jafage
title: Bring the v0.12 landing documents up to date for a merged, unreleased main
kind: task
status: closed
priority: 2
version: 4
delegate: claude-code@spud10.local
labels:
  - release:v0.12.0
dependencies: []
parent_id: is-01m402dbhn3zsc1h896f3xnrsq
hold: null
hold_until: null
created_at: 2026-10-26T15:28:55.427Z
updated_at: 2026-11-04T17:14:29.576Z
started_at: 2026-11-01T16:05:50.079Z
closed_at: 2026-11-04T17:14:29.576Z
close_reason: "Scoped implementation independently reviewed and tested; owning feature PRs are actually merged. Final main https://github.com/jlevy/metabrowser/commit/db52ec09cf839269da3a56fd396e44f3092995a9 includes account fix https://github.com/jlevy/metabrowser/pull/297 and documentation https://github.com/jlevy/metabrowser/pull/298, with final manual acceptance and per-issue qualifications checked. Individual source, test, review and merge evidence: ACTION-PLAN.json SHA-256 d0867a696ee055cc27911e83c4f70744b419a3ca4a7a1218f0eeaf419dc37589. Future scope and historical dependency relationships remain open or preserved as recorded."
resolution: null
duplicate_of: null
---
The landing documents landed in #260 and now describe the state BEFORE the merge. They tell a reader there is a stack to land, gates owed on a stack tip, and #267 and #260 still to be appended to stack 218. The stack merged on 2026-10-04 and #268 landed above all of it.

Specifically out of date:

- docs/project/specs/active/plan-2026-09-22-v012-alpha-testing.md, the Landing status section: rewrite for a merged main that is not yet released, keeping the "these commands win" framing.
- docs/project/specs/active/plan-2026-09-23-v012-thin-mirror.md: the Delivery table reads as forthcoming work, but steps 1 through 7 are all built and on main. Mark them landed and say what the Capability Map's Later column still means now.
- docs/project/reviews/review-2026-10-01-v012-stack-review-ledger.md: add the #268 row (storage split, the CI glob fix, the integrated page-connection work) and note that #262 is superseded rather than merged.
- docs/project/reviews/review-2026-10-01-v012-changes-to-existing-behavior.md: it is a dated sign-off record, so do not rewrite it, but it predates #268. The breaking cache and configuration XDG split is NOT on its list and must be added for the owner's sign-off, because it is a change to behavior v0.11.0 had.
- docs/qa-v012-repository-library.md: its status line still calls the stack unreleased-and-landing.

Do not restate anything make verify or check_parity.py can enforce, and cite the file or command for any count rather than writing a number into prose.

## Notes

2026-11-01: fixed in PR #272, open, CI green at its last read. Close when it merges; its required review has not run.
