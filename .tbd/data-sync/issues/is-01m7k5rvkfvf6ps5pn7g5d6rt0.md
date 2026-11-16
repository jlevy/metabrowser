---
type: is
id: is-01m7k5rvkfvf6ps5pn7g5d6rt0
title: "macOS app: launch the built development app in macos-app.yml"
kind: task
status: open
priority: 3
version: 1
spec_path: docs/project/specs/active/plan-2026-11-16-macos-app-publishing.md
labels: []
dependencies: []
parent_id: is-01m7k1vctj6d370jg7hqdps4hk
created_at: 2026-11-16T21:56:19.694Z
updated_at: 2026-11-16T21:56:19.694Z
---
Phase 2 of the publishing plan (PR #485 A16). After make macos-app, macos-app.yml opens the development bundle on a scratch folder, waits for its server to answer, quits the app, and checks that no server process is left, failing the job on any miss. No secrets, no signing. Done when the step passes in CI and fails on a deliberately broken launch in a test run.
