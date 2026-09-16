---
type: is
id: is-01m2mbre4d05eh8nhf8f27wtwa
title: "Phase 0C.1 review R2: bind browser harness to installed contract inventory"
kind: bug
status: closed
priority: 1
version: 3
spec_path: docs/project/specs/active/plan-2026-08-27-github-provider-and-pull-requests.md
labels:
  - phase:hosted-review-0c1
  - review
dependencies: []
parent_id: is-01m2krxbqajmpk9zhjm8berj18
created_at: 2026-09-16T05:41:42.668Z
updated_at: 2026-09-16T07:13:34.100Z
closed_at: 2026-09-16T07:13:34.100Z
close_reason: "Fixed in 614fef15793ff7cffd0c4e85a577342472fd9686, independently re-reviewed with no remaining findings, published in the PR #135 disposition map, and validated by green local and GitHub CI."
resolution: null
duplicate_of: null
---
Fable Medium: Node harness manually lists parser/corpus families and can drift from ArtifactContractSpec browser_parser_id/corpus_id. Make Python emit/pass the installed browser contract descriptor and make Node resolve exact exports/corpora/record selectors from it, then reconcile architecture rows so ProviderSyncManifest remains explicitly server-only rather than claiming a browser parser.
