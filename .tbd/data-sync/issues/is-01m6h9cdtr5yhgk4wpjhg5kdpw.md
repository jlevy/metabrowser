---
type: is
id: is-01m6h9cdtr5yhgk4wpjhg5kdpw
title: "PR #287 Qodo4458535273: honor rate limit before comparison fallback"
kind: bug
status: closed
priority: 2
version: 4
labels: []
dependencies: []
parent_id: is-01m6g59qm4ewjgek4vjmndcxrj
created_at: 2026-11-03T18:05:15.991Z
updated_at: 2026-11-03T20:17:09.816Z
closed_at: 2026-11-03T20:17:09.816Z
close_reason: "Completed by forward commits in the PR-support stack; independent reviews, rechecks and dispositions are published on the owning PRs. Final integration ea771741211193a387c1771e04df29b5a9698100 passed make verify (4712 Python, 9 expected skips, 373 transcripts), 8 public live tests, installed-wheel Chrome (22 actions, 25 unchanged checkout/Git fingerprints), and all 171 CI jobs across 19 current-head runs on 14 PRs. Final clean review: https://github.com/jlevy/metabrowser/pull/288#pullrequestreview-5758664799 . No PR merged."
resolution: null
duplicate_of: null
---
Medium https://github.com/jlevy/metabrowser/pull/287#discussion_r4458535273, review5757123686 at38ab13f1f8693a1b0478490258a35a7317ac1df9. files_refresh_wanted lets local comparison bypass GitHub rate limit, but refresh_pull_files falls through to GitHub if local manifest is truncated or unreadable. Prove zero gh calls when saved limit holds at actual network boundary, preserve successful local lists during the hold and fallback after expiry. Root owns integration, publication, closure and sync.

## Notes

Confirmed/fixed in f1ae7c61188a85c319cf3870cacb32bc62402a0b, direct38ab13f1. Worker tries local manifest first and checks saved rate limit at actual GitHub fallback boundary before active account or API. Held fallback raises existing typed error while original stamp/list remain unchanged. Real missing-store and actual truncated-manifest regressions failed pre-fix with fake gh calls; now zero gh while held, GitHub fallback after expiry works, and real local manifest succeeds during hold.3focused worker tests plus81affected pytest/24unchangedgoldens/full lint/types/hooks pass. Evidence in ready-state-287-38ab13f1/REPORT.json. Independent recheck/root integration/finalCI pending; root owns publication, closure and sync.

Continuing D1 sequence correction at 0b45a25110a4a65eeab942ab380af31f6cd976af, direct forward child f1ae7c61. Independent success→missing and success→real-truncated sequences reproduced three fake GH calls each before reset. Existing reset_at now carries the network hold independently of local succeeded/current-time outcome; repeated local success preserves the deadline, later fallback emits zero account/API calls and retains valid cached local rows/current envelope, exact expiry allows GitHub and clears reset. No new fields/aliases.136affected tests,3extra malformed/cache-failure controls,24unchangedgoldens,full lint/types/parity/contracts/hygiene and normal hooks pass. Original strict probe/raw failure preserved; new semantic controls reflect approved current-success plus independent-reset contract. Evidence: ready-state-287-sequence-f1ae7c61/REPORT.json. Independent recheck/root integration/final CI pending; root owns publication, closure and sync.
