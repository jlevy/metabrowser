---
type: is
id: is-01m2k1jnf5t6bgg340skd537hn
title: "Hosted review Phase 0B.3: add the scrubbed GitHub coverage oracle"
kind: task
status: open
priority: 1
version: 2
spec_path: docs/project/specs/active/plan-2026-08-27-github-provider-and-pull-requests.md
labels:
  - release:v0.11.0
  - stack:pr125
dependencies:
  - type: blocks
    target: is-01m2k1jq7ydswdag1x08n30hvn
parent_id: is-01m10vgw6vhq82cd495kvhh9gf
created_at: 2026-09-15T17:24:33.379Z
updated_at: 2026-09-15T17:24:35.192Z
---
Add tests/fixtures/github/oracle, a checked-in terminology-to-common-model mapping inventory, tests/test_github_coverage.py, and tests/test_github_mapping.py. Every common field must name a view, route, cache, or adapter consumer and be observed, derived, or explicitly optional with not_requested state. Recorded responses are scrubbed public evidence only, never runtime input or a second model. Include hostile metadata and future GitLab as a named contract consumer without speculative fields.
