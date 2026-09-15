---
type: is
id: is-01m2h9a03f8wvg3fk6crpmb71m
title: "PR #125 review C-R5: harden gh API arguments and response envelopes"
kind: bug
status: closed
priority: 1
version: 3
spec_path: docs/project/specs/active/plan-2026-08-27-github-provider-and-pull-requests.md
labels: []
dependencies: []
parent_id: is-01m2h984s9t8fhm2efg67nwmve
created_at: 2026-09-15T01:01:09.101Z
updated_at: 2026-09-15T01:38:09.794Z
closed_at: 2026-09-15T01:38:09.794Z
close_reason: "Fixed C-R5: specified fixed templates/documents, JSON stdin, typed percent-encoded REST builders, bounded included-response parsing, allowlisted headers, GraphQL error/null handling, GHES version behavior, and prohibited unsafe gh modes."
resolution: null
duplicate_of: null
---
PR #125 contracts C-R5. Fix endpoint and query text, prohibit placeholder and magic-field interpolation, use bounded JSON stdin or type-fixed raw fields, parse included status and allowlisted headers separately from bounded JSON, handle GraphQL errors, pin API versions, and add incompatible GHES states.
