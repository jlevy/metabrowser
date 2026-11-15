---
type: is
id: is-01m7dqret6mea79taytx6m775k
title: "Architecture: the map, parity registry, entry point, large-content rendering"
kind: task
status: in_progress
priority: 2
version: 2
spec_path: docs/project/specs/active/plan-2026-11-14-documentation-from-first-principles.md
labels: []
dependencies: []
parent_id: is-01m7dqmdjvjrgqd3vpqw3z3zdc
created_at: 2026-11-14T19:15:14.373Z
updated_at: 2026-11-15T05:56:41.340Z
---
Phase 2, PR 7: the map, the parity registry, the entry point, and large-content rendering.

- Split arch-views-models-routes.md: the map (about 250 lines: kinds, views, formats, route index) and arch-parity-registry.md (only the two tables devtools/check_parity.py:37 reads). Delete the route-contract prose the layer PRs copied out, and the parity prose the contributor PR copied into development.md. Move the paths devtools/check_parity.py and three tests read (test_parity_runtime.py, test_views_models_routes.py, test_check_parity.py).
- Rewrite docs/architecture.md (660 to about 250 lines) as the single entry point: the thesis, the layers with their module paths, a reading order, and a link to every architecture document. Delete material the layer PRs copied out (:7-78, :507-538), and folder composition (:100-252), URL and Markdown detail (:314-484), and filtering (:540-604).
- Cut docs/large-content-rendering.md (768 to about 250): delete what the diff and app PRs copied out; add a Status line (one is buried at :503); the limits table names its constants without restating their values; remove bead IDs (:503, :651).

Known errors to fix:
- docs/architecture.md :15 and :636 name inventory.py, which does not exist; :626-638 omit cache/, diff/, inventory_engine/, data/; :572 names collect_recent_entries, which exists only in a comment (settings.py:204); :407-444 describe _mb_ presentation keys without saying they are unbuilt.
- The map: :179 lists folder/* hooks that do not exist; :678 says one golden covers every kind (10 of 12 have one); :648-667 "Planned" holds 2 built and 6 retired rows; the comparison kind is missing (cli/show_cli.py:535).
- docs/large-content-rendering.md :472 gives DEFAULT_ACCENT_RUN_BUDGET as 60,000 runs; byte-format.js:65 sets 400000. :666-709 contradicts :116-127.
