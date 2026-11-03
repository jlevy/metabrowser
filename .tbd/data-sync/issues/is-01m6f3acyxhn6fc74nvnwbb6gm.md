---
type: is
id: is-01m6f3acyxhn6fc74nvnwbb6gm
title: Untrusted text on a trusted page
kind: task
status: in_progress
priority: 1
version: 3
spec_path: docs/project/specs/active/plan-2026-10-01-github-pulls-tab.md
delegate: claude-code@spud10
labels: []
dependencies: []
parent_id: is-01m2nz9gwd4wyxmrpx49cp9yck
hold: null
hold_until: null
created_at: 2026-11-02T21:40:49.244Z
updated_at: 2026-11-03T07:15:48.639Z
started_at: 2026-11-03T07:01:15.387Z
---
The hostile-content corpus under both profiles with mutation checks, and a dedicated security review, since a trusted folder's page has no Content-Security-Policy behind the allowlist.

## Notes

2026-11-03 HANDOFF: on wip/pulls-5-checkout (24a95778). test_pull_request_text_is_inert_under_both_profiles serves a checkout's hostile record: title, body, branch, label, a comment and a review, carrying HOSTILE_COMMENT and the inert-html-hostile-links corpus. It runs under trusted, with no CSP (asserted), and under untrusted. Both answer the same markup with no allowlist violation; refused links come back as bare <a>; the record's texts stay JSON strings. The mutation check is in the test: with harden removed, every text has violations. The dedicated security review has not happened. For the reviewer: the folder server's diff comparison route runs git in the checkout (existing behaviour); the checkout page never calls it. See mb-cbak.
