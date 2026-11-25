---
type: is
id: is-01m2ktt8fsnkz860ze0f0ps2gm
title: "Hosted releases R4: bounded index and Releases navigation"
kind: feature
status: closed
priority: 2
version: 9
spec_path: docs/project/specs/done/plan-2026-08-27-github-provider-and-pull-requests.md
labels:
  - hosted-releases
dependencies:
  - type: blocks
    target: is-01m2ktnhjgw0bsgcaw6e8h9x2e
parent_id: is-01m2ktnhjgw0bsgcaw6e8h9x2e
child_order_hints:
  - is-01m2kttf7tse7rs1nwrk9m3jbj
  - is-01m2kttm2pz1n1s6t0pmv6ps95
created_at: 2026-09-16T00:45:36.630Z
updated_at: 2026-11-25T02:40:21.992Z
closed_at: 2026-11-14T18:44:46.292Z
close_reason: "Obsolete as written: R4 publishes the retired ReleaseIndex contract on top of R3; the Releases list stays part of mb-7srn until re-planned on the thin mirror."
resolution: canceled
duplicate_of: null
---
One formal PR stacked on green R3. Publish bounded ReleaseIndex observations without hydrating bodies or assets, add a repository-scoped Releases virtual collection, reuse generic paging/virtualization/restoration/disposal, select direct release resources from summary rows, and optionally project releases into repository activity without making the projection authoritative.
