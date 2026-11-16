---
type: is
id: is-01m7hfr18ftecxypnspcpyr4f8
title: "PR #472 A7: Chrome sessions sleep for the travel and bound rows by a literal 900"
kind: bug
status: closed
priority: 3
version: 2
labels: []
dependencies: []
parent_id: is-01m7hcjx7q1sk1bp90ba48mdha
created_at: 2026-11-16T06:12:09.614Z
updated_at: 2026-11-16T06:13:22.247Z
closed_at: 2026-11-16T06:13:22.246Z
close_reason: "fixed in e6c6a67aa (PR #472 review A)"
resolution: null
duplicate_of: null
---
tests/dom/diff-summary-chrome.mjs:129, git-commit-summary-chrome.mjs:124, github-pull-header-chrome.mjs:140 sleep; tests/test_changed_file_rows_chrome.py:244 bounds by 900 where the page is 813 px. Severity: Suggestion. PR #472, review A round 1: https://github.com/jlevy/metabrowser/pull/472#pullrequestreview-5915650916
