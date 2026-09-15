---
type: is
id: is-01m2h9a6bqbp6rftnrv9jf3fw8
title: "PR #125 review D-R2: reconcile clean and selected-ref dependency ownership"
kind: bug
status: closed
priority: 1
version: 3
spec_path: docs/project/specs/active/plan-2026-08-27-github-provider-and-pull-requests.md
labels: []
dependencies: []
parent_id: is-01m2h984s9t8fhm2efg67nwmve
created_at: 2026-09-15T01:01:15.507Z
updated_at: 2026-09-15T01:38:13.362Z
closed_at: 2026-09-15T01:38:13.361Z
close_reason: "Fixed D-R2: kept is_clean on serving/replacement/repair/purge rather than acquisition, assigned pure resolution to selection.py and network selected-ref fetching to jobs.py/mb-jlon, and aligned dependencies."
resolution: null
duplicate_of: null
---
PR #125 delivery D-R2. Keep staging acquisition independent of Git status and gate cache-hit serving and integrity on mb-u4mf. Give fetch_selected_ref to mb-jlon and make any-branch integration mb-2xq7 depend on it. Update docs, diagrams, functions, and bead dependencies.
