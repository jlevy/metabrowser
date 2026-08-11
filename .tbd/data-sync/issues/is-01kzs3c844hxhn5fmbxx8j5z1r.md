---
type: is
id: is-01kzs3c844hxhn5fmbxx8j5z1r
title: Default server logs are too verbose for large roots
kind: bug
status: closed
priority: 1
version: 3
labels: []
dependencies: []
parent_id: is-01kzrtbtsh9k6p8x84rta84y4p
created_at: 2026-08-11T19:04:21.379Z
updated_at: 2026-08-11T19:24:57.643Z
closed_at: 2026-08-11T19:24:57.642Z
close_reason: Default large-root output now suppresses routine timings, expected indexing races, protected-directory skips, and lifecycle chatter; slow work and actionable failures remain visible. Regression tests, the real home-root run, make verify, pre-push, and PR CI all pass.
---
Browsing a large root such as a home directory floods the default terminal with routine microsecond timings and expected inventory generation races. Make default output quiet while retaining actionable failures and genuinely slow-operation diagnostics. Keep detailed lifecycle and request traces available through explicit logging controls, and add regression coverage for the attached log patterns.
