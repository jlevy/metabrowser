---
type: is
id: is-01m6f1c2ezhdeyv58q2cakvn4y
title: "PR #272 https://github.com/jlevy/metabrowser/pull/272#discussion_r4436441172: review-github-pr letter re-check omits the linked-issue and review-doc sweeps"
kind: bug
status: open
priority: 2
version: 4
delegate: claude-code@spud10
labels: []
dependencies: []
parent_id: is-01m6f1c0tknva4bd436kj524e0
hold: null
hold_until: null
created_at: 2026-11-02T21:06:46.878Z
updated_at: 2026-11-02T21:15:59.053Z
started_at: 2026-11-02T21:06:52.427Z
---
Unmarked bot comment, bot severity Medium. .tbd/doc-forks/base/shortcut/review-github-pr.md:223-225, docs/tbd/shortcuts/review-github-pr.md. Upstream wording in tbd 0.10.0.

## Notes

Deferred from https://github.com/jlevy/metabrowser/pull/272#discussion_r4436441172. Upstream tbd wording: step 9 of review-github-pr repeats only the formal review and PR comment sweeps of step 5 when it re-checks the review letter; the linked-issue and in-repo review doc sweeps are not repeated. Text is verbatim in tbd 0.10.0 (dist/docs/shortcuts/standard/review-github-pr.md), so the fix is upstream, and tbd docs update --merge brings it here. Not yet reported upstream: filing needs the owner's or coordinator's go-ahead. Same pass can tidy create-or-update-pr-simple step 6, whose 'if step 3 settled on separate PRs because github-stacked-prs is not granted' has no case in step 3 under an explicit request (https://github.com/jlevy/metabrowser/pull/272#discussion_r4436441170, rebutted in mb-xsz9).
