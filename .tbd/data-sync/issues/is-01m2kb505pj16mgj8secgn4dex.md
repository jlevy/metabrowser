---
type: is
id: is-01m2kb505pj16mgj8secgn4dex
title: "Hosted review Phase 0B.1f: model query-keyed change request indexes"
kind: task
status: closed
priority: 1
version: 6
spec_path: docs/project/specs/active/plan-2026-08-27-github-provider-and-pull-requests.md
labels:
  - release:v0.11.0
  - phase:hosted-review-0b1
dependencies:
  - type: blocks
    target: is-01m2kb5g8pf551djgfmf9kcm87
  - type: blocks
    target: is-01m2ktj7tvearg7zwk2nkz6cry
parent_id: is-01m2k1jj8edebds7zv8abfc917
created_at: 2026-09-15T20:11:51.349Z
updated_at: 2026-09-16T01:31:33.312Z
closed_at: 2026-09-16T01:31:33.311Z
close_reason: Implemented, independently reviewed with no remaining findings, and validated by make verify (2193 passed, 1 skipped; 124 golden tests; audits and distribution checks clean).
resolution: null
duplicate_of: null
---
Add ChangeRequestIndexQuery, IndexBounds, IndexSort, ChangeRequestIndexRow, ChangeRequestIndex, validate/dump entry points, change_request_index_query_key(), validate_change_request_index_row_identity(), and validate_change_request_index_resource_set() to hosted_review/models.py. Hash a domain-separated canonical JSON array over provider/instance/repository, filter, sort/tie-break, and declared bounds; exclude cursor, auth context, retrieval metadata, and results. Keep the reusable index snapshot to query plus bounded ordered rows. Put tagged continuations, contiguous page evidence, observation window, collection coverage, and remote consistency in the enclosing ResourceSet. Enforce stable-ID uniqueness, temporal ordering, provider-snapshot consistency, and direct/index identity agreement. Keep bodies, reviews, checks, refs, threads, and patches out of index rows.

## Notes

Implemented query-keyed ChangeRequestIndex contracts, bounds, consistency and continuation semantics, raw observed-count bounds, duplicate/identity validation, corpus coverage, and tests.
