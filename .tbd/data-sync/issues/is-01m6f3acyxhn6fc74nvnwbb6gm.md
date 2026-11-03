---
type: is
id: is-01m6f3acyxhn6fc74nvnwbb6gm
title: Untrusted text on a trusted page
kind: task
status: closed
priority: 1
version: 4
spec_path: docs/project/specs/active/plan-2026-10-01-github-pulls-tab.md
delegate: claude-code@spud10
labels: []
dependencies: []
parent_id: is-01m2nz9gwd4wyxmrpx49cp9yck
hold: null
hold_until: null
created_at: 2026-11-02T21:40:49.244Z
updated_at: 2026-11-03T20:17:10.215Z
started_at: 2026-11-03T07:01:15.387Z
closed_at: 2026-11-03T20:17:10.215Z
close_reason: "Completed by forward commits in the PR-support stack; independent reviews, rechecks and dispositions are published on the owning PRs. Final integration ea771741211193a387c1771e04df29b5a9698100 passed make verify (4712 Python, 9 expected skips, 373 transcripts), 8 public live tests, installed-wheel Chrome (22 actions, 25 unchanged checkout/Git fingerprints), and all 171 CI jobs across 19 current-head runs on 14 PRs. Final clean review: https://github.com/jlevy/metabrowser/pull/288#pullrequestreview-5758664799 . No PR merged."
resolution: null
duplicate_of: null
---
The hostile-content corpus under both profiles with mutation checks, and a dedicated security review, since a trusted folder's page has no Content-Security-Policy behind the allowlist.

## Notes

2026-11-03 HANDOFF: on wip/pulls-5-checkout (24a95778). test_pull_request_text_is_inert_under_both_profiles serves a checkout's hostile record: title, body, branch, label, a comment and a review, carrying HOSTILE_COMMENT and the inert-html-hostile-links corpus. It runs under trusted, with no CSP (asserted), and under untrusted. Both answer the same markup with no allowlist violation; refused links come back as bare <a>; the record's texts stay JSON strings. The mutation check is in the test: with harden removed, every text has violations. The dedicated security review has not happened. For the reviewer: the folder server's diff comparison route runs git in the checkout (existing behaviour); the checkout page never calls it. See mb-cbak.
