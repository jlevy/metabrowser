---
type: is
id: is-01m0txjrbpvp29dgrtbv3wvpmy
title: "PR #74 review MB74-C6: pin one as_of_ns across paged assembly"
kind: bug
status: open
priority: 1
version: 1
spec_path: docs/project/specs/active/plan-2026-08-23-inventory-provider-refactor-and-fdu-adoption.md
labels: []
dependencies: []
parent_id: is-01m0txhaybmj82ym2wcm85zz0b
created_at: 2026-08-24T22:17:13.846Z
updated_at: 2026-08-24T22:17:13.846Z
---
Source: confirm-only finding at https://github.com/jlevy/metabrowser/pull/74#issuecomment-5401198953. docs/project/architecture/arch-inventory-provider.md:86 and :115 define explicit recency time but do not state that every page in one version-pinned assembly must reuse the same as_of_ns. Make that invariant explicit and add a provider/coordinator harness case.
