---
type: is
id: is-01m7jqg4wcesq9xk1kteqtnape
title: "PR #479 A1: summary-wait regression fix belongs in #478"
kind: bug
status: closed
priority: 2
version: 2
labels: []
dependencies: []
parent_id: is-01m7jp047k8p38s3q818n9hvc1
created_at: 2026-11-16T17:46:54.220Z
updated_at: 2026-11-16T18:32:11.128Z
closed_at: 2026-11-16T18:32:11.127Z
close_reason: "fixed in #478: the summary-wait repair is 7e012e178 on claude/comparison-cache (in #478 at d9782d01e), merged up into #479 at 151664e02; this layer keeps its change parameter and ONE_STATUS width check; test_github_pull_header_chrome.py 10 passed at 151664e02"
resolution: null
duplicate_of: null
---
Medium. tests/dom/github-pull-header-chrome.mjs:344-348, commit 52c618d1b; layer #478. Review A (round 1) on PR #479: https://github.com/jlevy/metabrowser/pull/479#pullrequestreview-5924585584
