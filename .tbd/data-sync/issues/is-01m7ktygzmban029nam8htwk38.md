---
type: is
id: is-01m7ktygzmban029nam8htwk38
title: "PR #496 review A10: Q5 overstates what a required ci-ok stops"
kind: bug
status: closed
priority: 3
version: 2
spec_path: docs/project/specs/active/plan-2026-11-16-fast-ci.md
labels: []
dependencies: []
parent_id: is-01m7ktycr1m7798eaqhyky3qnr
created_at: 2026-11-17T04:06:25.524Z
updated_at: 2026-11-17T04:08:34.097Z
closed_at: 2026-11-17T04:08:34.096Z
close_reason: "Fixed in 8b4da0cb: Q5 says macos-app.yml is a separate path-filtered workflow outside ci-ok, so a red macOS job still does not block a merge; the coverage table says so too."
resolution: null
duplicate_of: null
---
plan:598-601. macos-app.yml is a separate path-filtered workflow outside ci-ok, so a red macOS job does not block a merge.
