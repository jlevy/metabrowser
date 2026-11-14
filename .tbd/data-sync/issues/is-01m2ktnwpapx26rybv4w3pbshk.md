---
type: is
id: is-01m2ktnwpapx26rybv4w3pbshk
title: "Hosted releases R0 implementation: models, codecs, profiles, and corpora"
kind: task
status: closed
priority: 2
version: 6
spec_path: docs/project/specs/active/plan-2026-08-27-github-provider-and-pull-requests.md
labels:
  - hosted-releases
dependencies:
  - type: blocks
    target: is-01m2ktp3wnzbzmr1cvb51qtptf
parent_id: is-01m2ktnpypp52bxemwarsz57j6
created_at: 2026-09-16T00:43:13.481Z
updated_at: 2026-11-14T18:42:40.570Z
closed_at: 2026-11-14T18:42:40.568Z
close_reason: "Obsolete as written: the R0 implementation targets provider_resources and hosted-review artifact codecs that #246 removed (kept only on draft #247); a thin-mirror re-plan under mb-7srn would file new beads."
resolution: canceled
duplicate_of: null
---
Implement Release R0 in builtin_plugins/hosted_releases: release_models.py defines Release, ReleaseAsset, ReleaseIndex and validators; artifacts.py defines serialize_release_artifact, parse_release_artifact, serialize_release_asset_artifact, parse_release_asset_artifact, serialize_release_index_artifact, parse_release_index_artifact, and release_snapshot_identity; contracts.py and resource_profiles.py declare Release/v1 frontmatter-md plus ReleaseAsset/v1 and ReleaseIndex/v1 pure-yaml contracts and bounded 0..N assets with explicit partial/truncation evidence; hosted-releases-model.js defines parseRelease, parseReleaseAsset, and parseReleaseIndex. Add three conformance corpora, Python/browser tests, architecture-map entries, and distribution inventory. Reuse provider_resources without importing hosted_review.
