---
type: is
id: is-01m2has35syva59k9g364zn2nt
title: "PR #125 review N-R1: give review summary prose an authoritative artifact"
kind: bug
status: closed
priority: 2
version: 3
spec_path: docs/project/specs/active/plan-2026-08-27-github-provider-and-pull-requests.md
labels: []
dependencies: []
parent_id: is-01m2h984s9t8fhm2efg67nwmve
created_at: 2026-09-15T01:26:52.343Z
updated_at: 2026-09-15T01:38:12.592Z
closed_at: 2026-09-15T01:38:12.591Z
close_reason: "Fixed N-R1: Review/v1 is now a frontmatter-md artifact with machine-authoritative YAML and an optional Markdown summary body, including empty-body hashing, GitHub mapping, browser validation, and body/no-body fixtures."
resolution: null
duplicate_of: null
---
Closure review N-R1. Review/v1 currently models only disposition while GitHub review submissions may carry their own Markdown summary body, distinct from top-level PR comments and inline review comments. Make Review/v1 a frontmatter-md artifact: YAML owns identity, author, disposition, lifecycle, timestamps, and relationships; the optional Markdown body owns review prose. Add body/no-body fixtures, mapping coverage, browser validation, and renderer treatment.
