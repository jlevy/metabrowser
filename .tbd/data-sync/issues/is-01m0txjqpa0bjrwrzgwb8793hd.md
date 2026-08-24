---
type: is
id: is-01m0txjqpa0bjrwrzgwb8793hd
title: "PR #74 review MB74-C4: generalize semantic configuration fingerprints"
kind: bug
status: closed
priority: 1
version: 3
spec_path: docs/project/specs/active/plan-2026-08-23-inventory-provider-refactor-and-fdu-adoption.md
labels: []
dependencies: []
parent_id: is-01m0txhaybmj82ym2wcm85zz0b
created_at: 2026-08-24T22:17:13.161Z
updated_at: 2026-08-24T22:36:11.346Z
closed_at: 2026-08-24T22:36:11.345Z
close_reason: "Fixed: EngineVersion now carries a provider-composed semantic_fingerprint; maintained docs define the exact multi-component combination and validators use the generalized identity."
resolution: null
duplicate_of: null
---
Source: https://github.com/jlevy/metabrowser/pull/74#issuecomment-5401198953. docs/project/architecture/arch-inventory-provider.md:67 defines one registry fingerprint while FDU has independently cache-relevant type-rule, tag-rule, and reducer fingerprints. Define the version identity as semantic-configuration fingerprints or a specified combined fingerprint so the adapter translation is contractual and incompatible caches fail closed.
