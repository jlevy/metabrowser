---
type: is
id: is-01m7k5kgqh9xm6hnsdbh2p3fz7
title: "PR #485 A12: Linting the cask (mb-eoez) runs Homebrew in CI without a supply-chain review"
kind: bug
status: closed
priority: 3
version: 3
spec_path: docs/project/specs/active/plan-2026-11-16-macos-app-publishing.md
delegate: claude-code@spud10.local
labels: []
dependencies: []
parent_id: is-01m7k1vctj6d370jg7hqdps4hk
hold: null
hold_until: null
created_at: 2026-11-16T21:53:24.720Z
updated_at: 2026-11-16T22:10:01.090Z
started_at: 2026-11-16T21:53:40.336Z
closed_at: 2026-11-16T22:10:01.089Z
close_reason: "Fixed in 83ef69fc3: mb-eoez sets HOMEBREW_NO_AUTO_UPDATE=1, records the Homebrew review in SUPPLY-CHAIN-SECURITY.md, keeps Homebrew out of the release workflow, and defines the negative test as a malformed url stanza."
resolution: null
duplicate_of: null
---
Low. PLAN:493-495, :510; SUPPLY-CHAIN-SECURITY.md:3-4. Fix: record the review, set HOMEBREW_NO_AUTO_UPDATE=1, keep Homebrew out of the release workflow, define the negative test as a style or offline-audit failure. Review A (round 1) of PR #485: https://github.com/jlevy/metabrowser/pull/485#pullrequestreview-5928293258
