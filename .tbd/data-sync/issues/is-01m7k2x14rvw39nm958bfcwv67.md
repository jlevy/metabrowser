---
type: is
id: is-01m7k2x14rvw39nm958bfcwv67
title: "macOS app: lint the generated Homebrew cask in CI"
kind: task
status: open
priority: 3
version: 3
spec_path: docs/project/specs/active/plan-2026-11-16-macos-app-publishing.md
labels: []
dependencies:
  - type: blocks
    target: is-01m748xzfj0nvstrsj9766877c
parent_id: is-01m7k1vctj6d370jg7hqdps4hk
created_at: 2026-11-16T21:06:10.711Z
updated_at: 2026-11-16T22:07:28.188Z
---
Phase 2 of the publishing plan. macos-app.yml runs brew style and an offline brew audit --cask on the cask the release rehearsal renders, in a scratch tap, with HOMEBREW_NO_AUTO_UPDATE=1, so a template change Homebrew would reject fails before a release. Homebrew otherwise updates itself on first use and installs its own Ruby gems for style, so record its review in SUPPLY-CHAIN-SECURITY.md first; Homebrew never runs in the release workflow (PR #485 A12). The cask itself ships after the alpha's first round of feedback (owner, 2026-11-16, Q5); the lint can land before. Done when the step passes on the rehearsal cask and fails, in a test run, on a cask with a malformed url stanza that brew style or the offline audit reports.
