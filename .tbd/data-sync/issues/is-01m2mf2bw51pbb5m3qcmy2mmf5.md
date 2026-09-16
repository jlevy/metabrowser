---
type: is
id: is-01m2mf2bw51pbb5m3qcmy2mmf5
title: Resolve every built-in conformance selector against embedded evidence
kind: bug
status: closed
priority: 2
version: 2
spec_path: docs/project/specs/active/plan-2026-08-27-github-provider-and-pull-requests.md
labels:
  - phase-0c1
  - review
dependencies: []
parent_id: is-01m2krxbqajmpk9zhjm8berj18
created_at: 2026-09-16T06:39:33.764Z
updated_at: 2026-09-16T07:13:34.399Z
closed_at: 2026-09-16T07:13:34.399Z
close_reason: "Fixed in 614fef15793ff7cffd0c4e85a577342472fd9686, independently re-reviewed with no remaining findings, published in the PR #135 disposition map, and validated by green local and GitHub CI."
resolution: null
duplicate_of: null
---
Fable R19: browser expected-case counts reused the same filter without proving selectors exist or select cases, and server-only selectors were not resolved. Add inventory-driven evidence tests for every embedded corpus, require nonempty resolved cases, and run selected valid/invalid mutations through installed structural and semantic validation.
