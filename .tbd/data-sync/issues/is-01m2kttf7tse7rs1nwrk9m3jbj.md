---
type: is
id: is-01m2kttf7tse7rs1nwrk9m3jbj
title: "Hosted releases R4 implementation: discovery cache and virtual collection"
kind: task
status: open
priority: 2
version: 5
spec_path: docs/project/specs/active/plan-2026-08-27-github-provider-and-pull-requests.md
labels:
  - hosted-releases
dependencies:
  - type: blocks
    target: is-01m2kttm2pz1n1s6t0pmv6ps95
parent_id: is-01m2ktt8fsnkz860ze0f0ps2gm
created_at: 2026-09-16T00:45:43.546Z
updated_at: 2026-09-16T01:24:57.863Z
---
Implement Release R4 navigation: github/release_queries.py build_release_index_request owns the bounded list request and consumes R1 map_github_release_row; hosted_releases/service.py list_releases and refresh_release_index publish ReleaseIndex/v1; hosted-releases-panel.js createReleasesPanel, loadIndexPage, openRelease, restoreReleaseSelection, replaceRoot, and dispose reuse the generic virtual collection controller. Add pagination, truncation, offline, counts, restoration, replacement, disposal, CLI, browserless golden, parity-map, and distribution evidence.
