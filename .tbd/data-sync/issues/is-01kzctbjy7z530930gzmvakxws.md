---
type: is
id: is-01kzctbjy7z530930gzmvakxws
title: Gated rename and trash via POST /api/mutate with nav context-menu actions
kind: feature
status: open
priority: 2
version: 3
spec_path: docs/project/specs/active/plan-2026-08-06-menu-primitives-and-file-actions.md
labels: []
dependencies: []
created_at: 2026-08-07T00:35:49.318Z
updated_at: 2026-08-07T00:52:49.985Z
---
Phase 2 of the menu-primitives plan (see spec). --allow-edits / METAB_ALLOW_EDITS gate (off by default), CAPABILITIES block in client_settings_dict(), persistent edit-mode badge. mutations.py: regular files only; re-resolve + containment immediately before acting; name validation; no-overwrite; OPTIONAL expected_revision guard (stale_revision only when supplied — no token-issuance plumbing); structured outcomes incl io_error with causes preserved. Trash DECIDED: served-root-local quarantine .metabrowser-trash/<timestamp>-<serial>/<relative-path>, ignore-filtered from tree/inventory/catalog, UI says 'Metabrowser trash' never 'Trash'; send2trash rejected for now (cool-off). POST /api/mutate with rename/trash + cross-site hardening: reject non-application/json Content-Type and cross-site Sec-Fetch-Site (drive-by localhost POST). Publish via inventory event path; re-target preview on rename of open file; explicit removed state on trash of it. Add first text-button pair (.btn, .btn.destructive) for the confirm dialog. Bind F2/Delete on focused row to the same descriptors; hints via .menu-item-hint. Docs: capability, quarantine semantics, trusted-local warning.
