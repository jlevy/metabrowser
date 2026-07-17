---
type: is
id: is-01kxhv98rvybz9qh7xv5y5q7wz
title: "PR #2 review R2: make git ignored-path protocol NUL-safe"
kind: bug
status: closed
priority: 3
version: 3
labels: []
dependencies: []
parent_id: is-01kxhv6wpfmr1b7m1dssdrkn48
created_at: 2026-07-15T02:56:50.458Z
updated_at: 2026-07-15T03:02:05.959Z
closed_at: 2026-07-15T03:02:05.959Z
close_reason: Implemented and regression-tested manager-specific Node pins plus NUL-safe git check-ignore handling; full make verify passed.
---
PR #2 R2 (Low): devtools/public_hygiene.py:56-72. Use git check-ignore's NUL-delimited stdin/stdout protocol so valid unusual filenames are preserved, and replace the raw timeout with a named constant.
