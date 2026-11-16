---
type: is
id: is-01m7hhgn2cvnck317qfrcp4fv6
title: "PR #474 A2: one-token claim for count numerals is false and unchecked"
kind: bug
status: in_progress
priority: 2
version: 2
delegate: claude-code@spud10
labels: []
dependencies: []
parent_id: is-01m7hg857dzfenxr1hee0jd9ka
hold: null
hold_until: null
created_at: 2026-11-16T06:43:04.907Z
updated_at: 2026-11-16T06:43:13.550Z
started_at: 2026-11-16T06:43:13.549Z
---
Medium. docs/design-system.md:421-424, styles.css:400-406, .git-commit-file-status styles.css:6707-6712, .heading-tally-figure styles.css:1694-1696, tests/test_design_vocabulary.py:2127-2162. Fix: .git-commit-file-status takes --count-numeral-weight; extend the test so --pull-number-weight is only on pull-number selectors and every count numeral reads --count-numeral-weight. Review A round 1 on PR #474: https://github.com/jlevy/metabrowser/pull/474#pullrequestreview-5915978133
