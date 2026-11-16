---
type: is
id: is-01m7k2x14rvw39nm958bfcwv67
title: "macOS app: lint the generated Homebrew cask in CI"
kind: task
status: open
priority: 3
version: 1
spec_path: docs/project/specs/active/plan-2026-11-16-macos-app-publishing.md
labels: []
dependencies: []
parent_id: is-01m7k1vctj6d370jg7hqdps4hk
created_at: 2026-11-16T21:06:10.711Z
updated_at: 2026-11-16T21:06:10.711Z
---
Phase 2 of the publishing plan. macos-app.yml runs brew style and brew audit --cask on the cask the release rehearsal renders, in a scratch tap, so a template change Homebrew would reject fails before a release. Done when the step passes on the rehearsal cask and fails on a deliberately broken one in a test run.
