---
type: is
id: is-01m2kb505pj16mgj8secgn4dex
title: "Hosted review Phase 0B.1f: model query-keyed change request indexes"
kind: task
status: open
priority: 1
version: 2
spec_path: docs/project/specs/active/plan-2026-08-27-github-provider-and-pull-requests.md
labels:
  - release:v0.11.0
  - phase:hosted-review-0b1
dependencies:
  - type: blocks
    target: is-01m2kb5g8pf551djgfmf9kcm87
parent_id: is-01m2k1jj8edebds7zv8abfc917
created_at: 2026-09-15T20:11:51.349Z
updated_at: 2026-09-15T20:12:07.829Z
---
Add ChangeRequestIndexQuery, IndexBounds, IndexSort, ChangeRequestIndexRow, tagged continuation, IndexPage, RemoteConsistency, ChangeRequestIndex, validate/dump entry points, and change_request_index_query_key() to hosted_review/models.py. Key canonical validated JSON over provider/instance/repository, filter, sort/tie-break, and declared bounds; exclude cursor, auth context, retrieval metadata, and page results. Enforce bounded ordered rows, stable-ID uniqueness, deterministic duplicate policy, contiguous page chain, result coverage, observation ordering, provider-snapshot token consistency, and identity agreement with directly addressed ChangeRequest records. Keep bodies, reviews, checks, refs, threads, and patches out of index rows.
