---
type: is
id: is-01m6g4n54pv6gbm7yzjxbskegg
title: "Follow-ups from review E on PR 283: merge-base edge cases and a kept error"
kind: task
status: closed
priority: 2
version: 5
delegate: claude-code@spud10.local
labels: []
dependencies: []
parent_id: is-01m6f3n89kn7ztmfhrzswxnsgz
hold: null
hold_until: null
created_at: 2026-11-03T07:23:24.693Z
updated_at: 2026-11-03T20:17:10.175Z
started_at: 2026-11-03T08:05:59.077Z
closed_at: 2026-11-03T20:17:10.175Z
close_reason: "Completed by forward commits in the PR-support stack; independent reviews, rechecks and dispositions are published on the owning PRs. Final integration ea771741211193a387c1771e04df29b5a9698100 passed make verify (4712 Python, 9 expected skips, 373 transcripts), 8 public live tests, installed-wheel Chrome (22 actions, 25 unchanged checkout/Git fingerprints), and all 171 CI jobs across 19 current-head runs on 14 PRs. Final clean review: https://github.com/jlevy/metabrowser/pull/288#pullrequestreview-5758664799 . No PR merged."
resolution: null
duplicate_of: null
---
From review E (follow-up, round 3) on PR 283 at e8b7ff3d, after f987d033 was reverted at 483e3a83.
1. Git before 2.45 can keep a redundant merge-base candidate when its reduction meets a commit it cannot read, which on a borrowing store whose lender collected an ancestor could give a non-best merge base. f987d033's counted check closed that but broke criss-cross histories, which have two best merge bases each outside the other's history (review E1). A correct check must accept any best merge base: for example, that every commit both tips reach outside the answer's history is itself an ancestor-free common ancestor, or compare with merge-base --all on a Git that errors on missing commits. Only reachable with Git < 2.45 and a collected ancestor.
2. Review E3: on a complete store, a rev-list --count walk (00c0f48b, run only when merge-base answers exit 1) that times out or overflows fails the whole pull read as git_failed, and a first open then keeps no record. Map a timeout to a typed answer and keep the parts already read. Measured: 2.8 to 3.0 s on a 200k-commit history against a 15 s bound.
3. Review E5: a pin_changed poll (e8b7ff3d) leaves an earlier error shown until the guard reloads; clear it or leave it, and say which.
4. Qodo's unanswered comment on lender.py:768: a pack without its index.
Not reviewed yet: merge 2a22035b, the page in Chrome under the untrusted profile, and three of review E's eight mutations.

## Notes

2026-11-03 independent-review integration at final tip 58270d69. E follow-ups implemented and independently reviewed in F: a51cc866 old/unknown-Git readable ancestry accepts complete criss-cross history; timeout/output-limit failures remain typed and preserve records;48c03f84 bounds regular pack-index validation and preserves uncertain refs;6ade0868 clears stale pin_changed/304 error. f987d033 stays forward-reverted and 00c0f48b retained. Owning #283 3cb49015 includes original published b29dc787 by an empty-tree forward merge. Final full verification, publication and remote CI are coordinator gates still pending; no PR merged.
