---
type: is
id: is-01m6h3s8en6hje5zrdtjbja9pk
title: "PR #283: classify failed Git object queries with damaged lender pack indexes"
kind: bug
status: closed
priority: 2
version: 4
delegate: checkout_design
labels: []
dependencies: []
parent_id: is-01m6g59qm4ewjgek4vjmndcxrj
created_at: 2026-11-03T16:27:25.012Z
updated_at: 2026-11-03T20:17:09.760Z
closed_at: 2026-11-03T20:17:09.760Z
close_reason: "Completed by forward commits in the PR-support stack; independent reviews, rechecks and dispositions are published on the owning PRs. Final integration ea771741211193a387c1771e04df29b5a9698100 passed make verify (4712 Python, 9 expected skips, 373 transcripts), 8 public live tests, installed-wheel Chrome (22 actions, 25 unchanged checkout/Git fingerprints), and all 171 CI jobs across 19 current-head runs on 14 PRs. Final clean review: https://github.com/jlevy/metabrowser/pull/288#pullrequestreview-5758664799 . No PR merged."
resolution: null
duplicate_of: null
---
Final Linux CI on both admitted Git versions reports failed instead of lender_missing when a lender .idx is a directory: cat-file exits128 mmap failure before collection_doubt. Catch only GitCommandError at the shared object-kind query; inspect bounded pack evidence only on that failure with collection_doubt(lender, []). Confirmed lender damage becomes LenderGoneError with original cause, unrelated failures remain original. No healthy-path scan or writes to lender/refs. Add actual directory-index plus healthy-index controls for tip negotiation and sweep, noncommand/no-scan controls; focused tests/lint/normalhooks and independent H review. Coordinator owns forward integration, push and sync.

## Notes

Implemented as 850961cdb5a3dad6a166658e2ef632882e86a5d3 on codex/pr-lender-index-error-01a1a051, direct child of owning #283 04f8b202314fc4bcaecc385872be8233e362045b. Shared _object_kinds catches only GitCommandError; failure-only collection_doubt(lender, []) checks bounded pack evidence, preserves original cause when classifying observed damage as LenderGoneError, and rethrows unrelated failures unchanged. All three preparation/negotiation/sweep call sites covered. Real directory-index tests plus healthy-index controls prove no lender/ref writes. Red:2 failed,5 passed/14.33s. Green:11 focused/23.01s;204 overlay/cache-update/full-clone/acquisition tests/276.59s. Full make lint-check and normal commit hooks pass; clean two-file branch, no lock changes. Durable evidence at linux-index-04f8b202 under the task review-evidence directory. Author self-review only; independent H pin sent, actual Linux CI validation still required. Parent reserves forward integration, push and sync.
