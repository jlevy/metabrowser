---
type: is
id: is-01m6hknzgxphza4kbk01qdxjka
title: Remove discarded patch payload from GitHub file-list fallback
kind: task
status: in_progress
priority: 3
version: 3
spec_path: docs/project/specs/active/plan-2026-10-01-github-pulls-tab.md
delegate: codex@spud10
labels: []
dependencies: []
parent_id: is-01m6f39t9zax1nbajkkasya6st
hold: null
hold_until: null
created_at: 2026-11-03T21:05:14.776Z
updated_at: 2026-11-03T21:47:47.089Z
started_at: 2026-11-03T21:47:46.051Z
---

## Notes

Payload audit at ea771741: ordinary file lists and diffs already come from Git when the store has exact endpoints. Only the unattached/truncated fallback downloads the REST file-list payload. A50-file public sample was378998decoded bytes, including331757bytes of discarded patch text; a minimal GraphQL equivalent was5605bytes but omits previous filenames for renames. A staged GraphQL/REST hybrid would lose progressive publication and add duplicate requests on rename cases. Preserve correct current behavior; this remains a Low optimization follow-up outside catalog delivery mb-m13a. No patch-free fallback implementation is claimed. Audit evidence is catalog-payload-ea771741/metrics.json and design-audit.json; no private repository or checkout content was used.
