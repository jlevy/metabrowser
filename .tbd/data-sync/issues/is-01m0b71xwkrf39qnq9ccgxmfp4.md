---
type: is
id: is-01m0b71xwkrf39qnq9ccgxmfp4
title: "Hosted review Phase 4: anchored review threads over comparisons"
kind: feature
status: deferred
priority: 1
version: 9
spec_path: docs/project/specs/active/plan-2026-08-27-github-provider-and-pull-requests.md
labels: []
dependencies:
  - type: blocks
    target: is-01m2kw2dcatp87s48y8ra11jp4
parent_id: is-01kzs5m38dz1egphfwf30c8h7n
created_at: 2026-08-18T19:54:57.298Z
updated_at: 2026-10-01T00:13:15.640Z
---
Implement provider-neutral ReviewThread and frontmatter ReviewComment views over a closed tagged ReviewAnchor union: file-only, one-line, and range forms with side/orientation, immutable comparison and revision IDs, path, and context fingerprint. GitHub is the first producer. Map only with sufficient Git identity and context; otherwise preserve the provider anchor as outdated, unresolved, or unmappable without inventing a line. Include file-level, outdated-range, deleted-file, and remapped fixtures; never extend File Diff Format.

## Notes

2026-09-30: deferred by the user's 2026-09-23 decision (thin-mirror plan, Decisions). Not part of v0.12; does not gate mb-n2ro. The design text predates the thin mirror (provider store, auth contexts, leases and SDK panels are retired); re-plan against the thin-mirror plan before starting.
