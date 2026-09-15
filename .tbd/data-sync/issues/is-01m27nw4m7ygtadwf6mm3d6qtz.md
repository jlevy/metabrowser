---
type: is
id: is-01m27nw4m7ygtadwf6mm3d6qtz
title: Reintroduce Markdown graph through a KPress-owned intent route
kind: feature
status: open
priority: 2
version: 3
spec_path: docs/project/specs/active/plan-2026-09-10-functional-ui-cli-parity.md
labels:
  - markdown
  - parity
  - performance
dependencies: []
parent_id: is-01m26hjjvhpcf49p2x1c3390kk
created_at: 2026-09-11T07:28:22.150Z
updated_at: 2026-09-14T23:28:09.694Z
---
Design and implement a server data route for Markdown graph analysis whose ordered link/resource intent manifest is produced by KPress's exact parser and sanitizer transaction, not a second Metabrowser grammar. The manifest must be bounded and atomic with complete/count/diagnostics, entity-decoded DOM-equivalent targets, and explicit source/output/target limits. Add a batch or cache-aware surface so large graphs do not require one full render per file; expose it through metab --api, add canonical golden conformance against final KPress DOM, and record linear-work plus retained-memory evidence at the maximum source and target bounds before restoring any browser facade.
