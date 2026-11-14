---
type: is
id: is-01m2ktvrasq8fxf38pn3yf1p8j
title: "Hosted releases: stack landing, retargeting, and post-merge verification"
kind: task
status: closed
priority: 2
version: 5
spec_path: docs/project/specs/active/plan-2026-08-27-github-provider-and-pull-requests.md
labels:
  - hosted-releases
dependencies:
  - type: blocks
    target: is-01m2ktnhjgw0bsgcaw6e8h9x2e
parent_id: is-01m2ktnhjgw0bsgcaw6e8h9x2e
created_at: 2026-09-16T00:46:25.624Z
updated_at: 2026-11-14T18:45:30.415Z
closed_at: 2026-11-14T18:45:30.414Z
close_reason: "Obsolete: landing owner for the retired R0-R4 release stack, which will not be built as designed; a re-plan under mb-7srn would define its own landing."
resolution: canceled
duplicate_of: null
---
Sole owner for landing the formal R0-R4 release PR stack. Record exact PR/base/head OIDs, wait for explicit merge approval, land in order, retarget or rebase each next PR after its base lands, recheck the exact phase diff, rerun make verify and final CI, and confirm main contains each layer. No implementation or publication bead may merge another phase.
