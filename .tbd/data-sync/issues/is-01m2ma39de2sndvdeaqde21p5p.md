---
type: is
id: is-01m2ma39de2sndvdeaqde21p5p
title: "Phase 0C.1 parity: Python browser schema and corpus agreement"
kind: task
status: closed
priority: 1
version: 4
spec_path: docs/project/specs/active/plan-2026-08-27-github-provider-and-pull-requests.md
labels:
  - phase:hosted-review-0c1
  - testing
dependencies: []
parent_id: is-01m2krx2resarv4h36yyeje2gj
created_at: 2026-09-16T05:12:41.129Z
updated_at: 2026-09-16T07:13:41.528Z
closed_at: 2026-09-16T07:13:41.528Z
close_reason: "Implemented in 614fef15793ff7cffd0c4e85a577342472fd9686: first-party SoftSchema dependency selection, installed capability registries, 16 enforced contracts, two profiles, cross-runtime evidence, and isolated distribution validation; make verify and GitHub CI are green."
resolution: null
duplicate_of: null
---
Extend production browser parsers and portable corpus harnesses so every browser-consumed Phase 0 contract agrees across Python model validation, JavaScript parsing, compiled enforced SoftSchema schemas, and named valid/invalid fixtures. Keep DOM/network-free and package all required schema assets.

## Notes

Browser-consumed surface is exactly 10 families: HostedRepository, ChangeRequestIndex, ChangeRequest, ChangeRequestComment, Review, ReviewThread, ReviewComment, Check, CommitStatus, RepositoryActivity. Six publication records remain server-only. Extend the DOM/network-free production parser and portable corpus dispatcher for the nine missing parser entry points; schemas are structural and semantic verdicts remain model-owned.
