---
type: is
id: is-01m2ktsfdmrdehcpvg9kqsg6yb
title: "Hosted releases R3 implementation: route, views, Source, and assets"
kind: task
status: open
priority: 2
version: 4
spec_path: docs/project/specs/active/plan-2026-08-27-github-provider-and-pull-requests.md
labels:
  - hosted-releases
dependencies:
  - type: blocks
    target: is-01m2ktsmf38rkaje935qzed4fp
parent_id: is-01m2kts81pnq5hh0xsb9465d22
created_at: 2026-09-16T00:45:10.963Z
updated_at: 2026-09-16T01:08:58.790Z
---
Implement Release R3 direct view: hosted_releases/routes.py release_resource, release_asset_resource, and hosted_resource_shell expose honest route-backed models; hosted-releases-view.js prepareReleaseView, mountReleaseView, and disposeReleaseView compose validated metadata, untrusted Markdown notes, tag revision, and assets through ResourceKindSpec and AddressSpaceSpec. Register assets/scripts/loading tiers, add hosted-releases-session production-JavaScript golden, CLI parity, hostile-content tests, lifecycle/disposal tests, map rows, and distribution checks.
