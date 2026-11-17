---
type: is
id: is-01m7kp7macfgf1hykxf2vy49ma
title: test_rm_directory_coalesces_descendant_removals is flaky under the Python provider
kind: bug
status: open
priority: 2
version: 1
spec_path: docs/project/specs/active/plan-2026-08-23-inventory-provider-refactor-and-fdu-adoption.md
labels: []
dependencies: []
parent_id: is-01m0r8xt95921dabcddjjm7csf
created_at: 2026-11-17T02:44:00.971Z
updated_at: 2026-11-17T02:44:00.971Z
---
The spike observed the one-envelope assertion failing intermittently with Python as well as fdu, because the live observer and the test's explicit refresh can land one removal in one batch or two. Replace it with an invariant that no published version exposes a half-removed subtree (D8). Evidence: explorations/fdu-provider-spike/.
