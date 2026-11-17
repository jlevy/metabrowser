---
type: is
id: is-01m7kp7macfgf1hykxf2vy49ma
title: test_rm_directory_coalesces_descendant_removals is flaky under the Python provider
kind: bug
status: closed
priority: 2
version: 2
spec_path: docs/project/specs/active/plan-2026-08-23-inventory-provider-refactor-and-fdu-adoption.md
labels: []
dependencies: []
parent_id: is-01m0r8xt95921dabcddjjm7csf
created_at: 2026-11-17T02:44:00.971Z
updated_at: 2026-11-17T03:23:04.243Z
closed_at: 2026-11-17T03:23:04.241Z
close_reason: "Not a bug: the spike harness leaked its fdu injection into the Python baseline. With the leak fixed, the test passed 32 of 32 runs for both providers (explorations/fdu-provider-spike/evidence/flake.json). The real finding, state-only provider commits surfacing as separate host envelopes during refresh, is tracked separately."
resolution: null
duplicate_of: null
---
The spike observed the one-envelope assertion failing intermittently with Python as well as fdu, because the live observer and the test's explicit refresh can land one removal in one batch or two. Replace it with an invariant that no published version exposes a half-removed subtree (D8). Evidence: explorations/fdu-provider-spike/.
