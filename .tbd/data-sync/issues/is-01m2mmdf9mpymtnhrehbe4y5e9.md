---
type: is
id: is-01m2mmdf9mpymtnhrehbe4y5e9
title: "Phase 0C.2 review R12: execute installed browser parser evidence from wheel and sdist"
kind: bug
status: in_progress
priority: 1
version: 4
spec_path: docs/project/specs/active/plan-2026-08-27-github-provider-and-pull-requests.md
labels:
  - phase:hosted-review-0c2
  - review
dependencies: []
parent_id: is-01m2kry0g3g8hbnhr896wvqeve
created_at: 2026-09-16T08:13:00.595Z
updated_at: 2026-09-16T08:22:54.324Z
---
The isolated wheel and sdist capability smokes validate Python corpus evidence and parser byte digests but do not execute the BrowserParserSpec bytes installed from each artifact. A packaging-specific malformed or Node-only parser can therefore pass. Export generic installed parser and corpus descriptors from each isolated artifact and run the same exact-byte browser-evidence helper against them, or provide an equivalent installed-artifact execution path. Add negative tests for invalid or Node-only parser bytes in both wheel and sdist smoke paths.

## Notes

Implemented R12 provider-neutral installed browser evidence for both wheel and sdist. Each isolated artifact install discovers and validates installed capability registries, materializes the exact installed browser-consumed parser and corpus bytes plus deterministic descriptors into a caller-owned temporary directory, and returns no source-tree package bytes. The distribution checker bounds every descriptor file to that handoff, invokes the same hardened repository Node harness, and requires its exact completion proof. Added focused coverage proving wheel and sdist both invoke the handoff/harness and both propagate node:fs parser rejection with the artifact name. Validation: tests/test_distribution_policy.py + tests/test_check_artifact_contracts.py 30 passed; Ruff check/format clean; BasedPyright 0 errors; git diff --check clean; real make build passed, including isolated wheel and sdist installed evidence/browser execution, doctor (2 providers, 16 contracts, 2 profiles), and API smoke. Initial sandboxed build lacked cache/network access; approved real rerun passed. Leave in_progress for PR disposition; no commit/push.
