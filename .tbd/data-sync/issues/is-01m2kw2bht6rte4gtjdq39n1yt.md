---
type: is
id: is-01m2kw2bht6rte4gtjdq39n1yt
title: "GitHub Phase 2B review: publish branch materialization PR"
kind: task
status: open
priority: 1
version: 9
spec_path: docs/project/specs/active/plan-2026-08-27-github-provider-and-pull-requests.md
labels:
  - release:v0.11.0
  - stack:publication
dependencies:
  - type: blocks
    target: is-01m2kw2bvjj5kcsczkz40cmhqx
  - type: blocks
    target: is-01kxry31k2e62styhj8t59jj12
  - type: blocks
    target: is-01m2h5an32kbkp6zfkhkjzq55f
  - type: blocks
    target: is-01m2h9jka5t3kw909ae7xefx8d
  - type: blocks
    target: is-01m2kvemzp183vrykz849c0s5a
  - type: blocks
    target: is-01m2h9jm62mjccx6x3bx0nct2a
  - type: blocks
    target: is-01m2h7gjbhrb9fdsbjjbcsf2n1
  - type: blocks
    target: is-01m2k713pxra1ns2fk3pcwrpb6
parent_id: is-01kzs5m38dz1egphfwf30c8h7n
created_at: 2026-09-16T01:07:30.490Z
updated_at: 2026-09-16T01:08:05.730Z
---
Independently review the selected-branch and detached-materialization slice, resolve all findings through the review shortcut, run make verify, and create or update one formal draft GitHub PR with gh stacked on the exact green Phase 2A head. Before closing, record the exact PR URL, base and head branch names, immutable base and head OIDs, review record, final green CI, and registration with mb-n2ro. Do not merge.
