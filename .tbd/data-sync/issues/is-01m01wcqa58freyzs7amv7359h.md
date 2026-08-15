---
type: is
id: is-01m01wcqa58freyzs7amv7359h
title: Move Log files into the Other file-type group
kind: feature
status: closed
priority: 2
version: 3
spec_path: docs/project/specs/done/plan-2026-08-13-shared-file-type-taxonomy-and-breakdowns.md
labels:
  - taxonomy
  - browser
dependencies: []
parent_id: is-01kxz2z9v1bbfcfmqstffkhvxp
created_at: 2026-08-15T04:55:26.788Z
updated_at: 2026-08-15T05:06:53.848Z
closed_at: 2026-08-15T05:06:53.847Z
close_reason: Moved Log files into Other, regenerated File Rollup Format revision 2 artifacts, kept the open-ended Other group out of fixed presets, updated docs and tests, validated live UI, and passed local and CI gates.
---
Remove the standalone Logs registry group and place the existing Log files semantic family under Other while preserving .log/.jsonl/.ndjson membership and content-family semantics. Increment the registry revision, regenerate all File Rollup Format artifacts, update filters, rollup and UI expectations and current docs, cover the change with TDD, validate live Overview behavior, and update PR #44.
