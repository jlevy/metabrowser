---
type: is
id: is-01m2mk1jrtcafrmy046gc53jt2
title: "Phase 0C.2 review R4: isolate installed-distribution Python smoke"
kind: bug
status: in_progress
priority: 1
version: 2
spec_path: docs/project/specs/active/plan-2026-08-27-github-provider-and-pull-requests.md
labels:
  - phase:hosted-review-0c2
  - review
dependencies: []
parent_id: is-01m2kry0g3g8hbnhr896wvqeve
created_at: 2026-09-16T07:49:02.361Z
updated_at: 2026-09-16T07:49:10.201Z
---
The isolated distribution smoke preserves ambient PYTHONPATH, PYTHONHOME, and PYTHONOPTIMIZE, runs plain python, and implements correctness checks with assert. This can import the checkout instead of the tested artifact and optimization can erase the checks. Scrub ambient path/home/optimization variables, run the interpreter in isolated mode, use explicit failures, and add a regression with poisoned PYTHONPATH and PYTHONOPTIMIZE proving the installed artifact is used and broken invariants still fail.
