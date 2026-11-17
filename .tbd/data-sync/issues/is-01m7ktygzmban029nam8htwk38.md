---
type: is
id: is-01m7ktygzmban029nam8htwk38
title: "PR #496 review A10: Q5 overstates what a required ci-ok stops"
kind: bug
status: open
priority: 3
version: 1
spec_path: docs/project/specs/active/plan-2026-11-16-fast-ci.md
labels: []
dependencies: []
parent_id: is-01m7ktycr1m7798eaqhyky3qnr
created_at: 2026-11-17T04:06:25.524Z
updated_at: 2026-11-17T04:06:25.524Z
---
plan:598-601. macos-app.yml is a separate path-filtered workflow outside ci-ok, so a red macOS job does not block a merge.
