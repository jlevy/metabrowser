---
type: is
id: is-01m2ktnpypp52bxemwarsz57j6
title: "Hosted releases R0: freeze provider-neutral release contracts"
kind: feature
status: closed
priority: 2
version: 10
spec_path: docs/project/specs/done/plan-2026-08-27-github-provider-and-pull-requests.md
labels:
  - hosted-releases
dependencies:
  - type: blocks
    target: is-01m2ktpzzzg5crhj0ggx8bbt1t
parent_id: is-01m2ktnhjgw0bsgcaw6e8h9x2e
child_order_hints:
  - is-01m2ktnwpapx26rybv4w3pbshk
  - is-01m2ktp3wnzbzmr1cvb51qtptf
created_at: 2026-09-16T00:43:07.606Z
updated_at: 2026-11-25T02:40:21.992Z
closed_at: 2026-11-14T18:44:51.354Z
close_reason: "Obsolete as written: R0 builds on the artifact-contract and resource-profile registries that the thin-mirror plan retired and #246 removed (kept only on draft #247); release browsing stays tracked by mb-7srn until re-planned."
resolution: canceled
duplicate_of: null
---
One formal no-network PR stacked on the completed hosted-resource registry foundation. Freeze Release/v1 as frontmatter-md, ReleaseAsset/v1 and ReleaseIndex/v1 as pure-yaml, direct-detail and bounded-index resource profiles, canonical identity/lifecycle/revision semantics, portable corpora, Python/browser/SoftSchema agreement, and architecture-map evidence. Exclude provider payloads and fields without consumers.

## Notes

2026-11-14 correction (PR #434 review A, A13): #246 removed the plugin-declared artifact contracts and resource profiles, the frontmatter-md profile among them, and the provider store; the core artifact-contract registry remains on main (plugin_loader/artifact_contracts.py) and admits only pure-yaml. Whether release browsing is re-planned or dropped is the open decision in mb-7srn.
