---
type: is
id: is-01m2ma343kxrg0701jkxweee60
title: "Phase 0C.1 registry: backend-only installed contracts and profiles"
kind: task
status: closed
priority: 1
version: 4
spec_path: docs/project/specs/active/plan-2026-08-27-github-provider-and-pull-requests.md
labels:
  - phase:hosted-review-0c1
  - registry
dependencies: []
parent_id: is-01m2krx2resarv4h36yyeje2gj
created_at: 2026-09-16T05:12:35.696Z
updated_at: 2026-09-16T07:13:41.499Z
closed_at: 2026-09-16T07:13:41.499Z
close_reason: "Implemented in 614fef15793ff7cffd0c4e85a577342472fd9686: first-party SoftSchema dependency selection, installed capability registries, 16 enforced contracts, two profiles, cross-runtime evidence, and isolated distribution validation; make verify and GitHub CI are green."
resolution: null
duplicate_of: null
---
Implement the smallest trusted backend-only plugin discovery and registry surface for artifact contracts and resource profiles. Do not require fake index.js/browser registration, do not persist module paths, and never let cached artifacts choose schemas or profiles. Reject duplicates and unknown contracts/profiles with focused discovery and installed-artifact tests.

## Notes

Use a separate trusted installed Python capability entry-point group, metabrowser.capabilities.v1, rather than a backend-only browser manifest. Browser manifests remain index.js/static/browser-SDK surfaces unchanged; capability factories return direct contract/profile objects and are discoverable only from installed distribution metadata, never operator directories or cached content. Add all-or-nothing capability discovery, immutable duplicate-rejecting registries, and neutral provider_resources profile types. Preserve stable contract/profile IDs across the later ownership move; module paths and declaration owners are not identity.
