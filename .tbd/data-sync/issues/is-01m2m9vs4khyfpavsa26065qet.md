---
type: is
id: is-01m2m9vs4khyfpavsa26065qet
title: "PR #134 review R7: harden public-data safety guards"
kind: bug
status: closed
priority: 2
version: 3
spec_path: docs/project/specs/active/plan-2026-08-27-github-provider-and-pull-requests.md
labels:
  - review
  - stack:pr134
dependencies: []
parent_id: is-01m2m9twtnpsc6m809wfefrpr9
created_at: 2026-09-16T05:08:35.090Z
updated_at: 2026-09-16T05:09:08.521Z
closed_at: 2026-09-16T05:09:08.520Z
close_reason: "Fixed in 18ef513a: all non-synthetic oracle and provenance files are scanned for secrets and unsupported URI schemes, public URLs are allowlisted, and the scrub claim is limited to long-form bodies."
resolution: null
duplicate_of: null
---
PR #134 delegated review R7. tests/test_github_coverage.py and tests/fixtures/github/oracle/manifest.json: scan every non-synthetic file, detect fine-grained PATs and unsupported URI schemes, use exact public allowlists, and narrow the prose-scrub claim to long-form bodies.
