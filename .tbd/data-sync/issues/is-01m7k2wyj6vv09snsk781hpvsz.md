---
type: is
id: is-01m7k2wyj6vv09snsk781hpvsz
title: "macOS app: read the notary log and fail on errors"
kind: task
status: open
priority: 2
version: 3
spec_path: docs/project/specs/active/plan-2026-11-16-macos-app-publishing.md
labels: []
dependencies:
  - type: blocks
    target: is-01m7k2xcrjxtgfe2mepxas1434
  - type: blocks
    target: is-01m7k2xdgr9b8sra4vrd372fe2
parent_id: is-01m7k1vctj6d370jg7hqdps4hk
created_at: 2026-11-16T21:06:08.069Z
updated_at: 2026-11-16T21:06:23.383Z
---
Phase 1 of the publishing plan. After each submission, notarize.sh reads the saved notary log JSON with plutil, fails on any issue of severity error, prints each warning with its path, and prints one line with the submission ID, status and issue counts for the release record. Done when scripts/test-scripts.sh runs the reader on fixture logs: accepted with no issues, accepted with a warning, and invalid with an error.
