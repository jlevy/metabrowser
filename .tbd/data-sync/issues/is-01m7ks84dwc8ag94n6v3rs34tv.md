---
type: is
id: is-01m7ks84dwc8ag94n6v3rs34tv
title: "Fix #490's failing check: tests/test_files_totals_stable_chrome.py:171, the 'none unknown slow 180px light' load fails in CI (test 3.13, run 44006918765); then merge main (CHANGELOG) and land #490"
kind: bug
status: open
priority: 1
version: 1
labels: []
dependencies: []
parent_id: is-01m7k4tntv9my4ynk41w81g0sj
created_at: 2026-11-17T03:36:43.195Z
updated_at: 2026-11-17T03:36:43.195Z
---
Find whether the clean folder's 180 px unknown load is a real move or a timing flake, and fix it at its cause. #490 also conflicts with main in CHANGELOG.md after #491; keep both entries.
