---
type: is
id: is-01m6h5a8rbfbgfvrv9q3g3jj62
title: "PR #283 Qodo4457437395: missing-object recovery guidance"
kind: bug
status: closed
priority: 2
version: 4
labels: []
dependencies: []
parent_id: is-01m6g59qm4ewjgek4vjmndcxrj
created_at: 2026-11-03T16:54:10.954Z
updated_at: 2026-11-03T20:17:09.783Z
closed_at: 2026-11-03T20:17:09.783Z
close_reason: "Completed by forward commits in the PR-support stack; independent reviews, rechecks and dispositions are published on the owning PRs. Final integration ea771741211193a387c1771e04df29b5a9698100 passed make verify (4712 Python, 9 expected skips, 373 transcripts), 8 public live tests, installed-wheel Chrome (22 actions, 25 unchanged checkout/Git fingerprints), and all 171 CI jobs across 19 current-head runs on 14 PRs. Final clean review: https://github.com/jlevy/metabrowser/pull/288#pullrequestreview-5758664799 . No PR merged."
resolution: null
duplicate_of: null
---
Medium review https://github.com/jlevy/metabrowser/pull/283#discussion_r4457437395 at04f8b202. The no-production-caller claim is false for the complete stack: #288 pulls._recover_comparison calls recover_comparison_objects before an explicit refresh. The lower generic diff/comparison message still names a pull-request Refresh even when the comparison has no PR. That wording is a real guidance issue; coordinate neutral generic wording with diff-sidekick owner, preserve typed object_unavailable and final PR recovery action. No source change here until ownership agreement.

## Notes

Fixed by coordinator in owning283 fad0b6150dd5c6e2cc3e7a88b2ccc88e114c666e: generic message now says An object in this comparison is missing. Repair the repository cache, then retry. No PR-specific Refresh promise. Final stack recovery caller already exists in upper288 pulls._recover_comparison. Coordinator reports normal hooks pass; integrated functional/finalCI pending. Public-safe full #283 draft covers this and other owned findings in durable bot-triage-281-283 evidence. Root owns publication/sync/closure.
