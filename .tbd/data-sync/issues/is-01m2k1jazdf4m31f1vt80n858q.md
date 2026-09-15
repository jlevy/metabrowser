---
type: is
id: is-01m2k1jazdf4m31f1vt80n858q
title: "Hosted review Phase 0A.4: add a portable ChangeRequest conformance corpus"
kind: task
status: closed
priority: 1
version: 6
spec_path: docs/project/specs/active/plan-2026-08-27-github-provider-and-pull-requests.md
labels:
  - release:v0.11.0
  - stack:pr125
dependencies:
  - type: blocks
    target: is-01m2k1jcp09qw704bx3hy87x9a
parent_id: is-01m10vgw6vhq82cd495kvhh9gf
created_at: 2026-09-15T17:24:22.633Z
updated_at: 2026-09-15T19:10:11.111Z
closed_at: 2026-09-15T19:10:11.110Z
close_reason: "Completed in draft PR #130: portable corpus, dormant browser parser, installed-distribution evidence, independent Fable review, full local verification, and final green GitHub CI. Post-stack landing is separately owned by mb-n2ro."
resolution: null
duplicate_of: null
---
Package src/metabrowser/data/hosted-review-format/change-request-conformance.json as the single portable base record plus named valid/invalid mutations, and exercise it from Python and exact production JavaScript. Cover open, draft, merged fork, unknown lifecycle, empty description, synthetic forge provider, extra keys, canonical URL/timestamp/integer boundaries, malformed object IDs, relationship mismatches, invalid envelopes, and wrong contract identity. Keep every case public-safe.

## Notes

Completed a 36-case packaged cross-runtime corpus plus frontmatter artifact failure tests. Fable review drove canonical UTC spelling, parser-independent ASCII HTTPS rules (including rejection of Unicode port digits), JS-safe integer bounds, integral JSON-number parity, generic invalid-case handling, and removal of the duplicate valid record.
