---
type: is
id: is-01m0nw8h8ch2ba2zsvkjqc8kcg
title: Measure the harness noise floor with an A/A control (S7)
kind: task
status: open
priority: 1
version: 1
spec_path: docs/project/specs/active/plan-2026-08-21-load-time-performance.md
labels: []
dependencies: []
parent_id: is-01m0k5wh7jgr0dgs5y78kwwke1
created_at: 2026-08-22T23:17:58.155Z
updated_at: 2026-08-22T23:17:58.155Z
---
Review suggestion S7. There is no measured noise floor. An A/A control -- the same build recorded under two labels -- measures the harness's own resolution directly, and compare could print it as a reference row so 'the ranges do not overlap' is judged against a known floor rather than an assumed one. Costs one extra serve/record pair per corpus. It would have answered the synthetic corpus's 42% 'regression' in exp-006 immediately.
