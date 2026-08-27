---
type: is
id: is-01m11xdn2nn2367wc63byc3z9h
title: "PR #31 review R11: porcelain v2 absence encoding not stated in the wire model"
kind: bug
status: closed
priority: 3
version: 2
spec_path: docs/project/specs/active/plan-2026-08-11-open-repo-from-git-url.md
labels: []
dependencies: []
parent_id: is-01m11xcje1qtw2aejrs5twn2vj
created_at: 2026-08-27T15:29:07.668Z
updated_at: 2026-08-27T15:44:29.341Z
closed_at: 2026-08-27T15:44:29.340Z
close_reason: "Fixed in dbe3206: absence encoding documented with the intent-to-add record, mapped to absent mode/OID, and named as a validator and parser-test case."
resolution: null
duplicate_of: null
---
plan-2026-08-26-git-status-and-working-tree-diffs.md:333-334. Absence arrives as all-zero OID and mode 000000 (verified on intent-to-add), not an omitted field.
