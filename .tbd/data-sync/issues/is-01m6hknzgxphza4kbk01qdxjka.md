---
type: is
id: is-01m6hknzgxphza4kbk01qdxjka
title: Remove discarded patch payload from GitHub file-list fallback
kind: task
status: open
priority: 3
version: 4
spec_path: docs/project/specs/active/plan-2026-10-01-github-pulls-tab.md
delegate: codex@spud10
labels: []
dependencies: []
parent_id: is-01m6f39t9zax1nbajkkasya6st
hold: null
hold_until: null
created_at: 2026-11-03T21:05:14.776Z
updated_at: 2026-11-14T18:41:51.209Z
started_at: 2026-11-03T21:47:46.051Z
---
When the store lacks a pull request's comparison, or its manifest is cut at MAX_MANIFEST_FILES, the changed-files job reads GitHub's REST list, repos/<owner>/<repo>/pulls/<n>/files, 100 files a page (builtin_plugins/github/pull_files_refresh.py), and drops each item's patch only after downloading it. The 2026-11-03 audit at ea771741 measured a 50-file public sample at 378,998 decoded bytes, 331,757 of them discarded patch text; a minimal GraphQL query was 5,605 bytes but omits previous filenames for renames, and a GraphQL/REST hybrid would lose progressive publication and add requests on renames. Find a patch-free read that keeps renames and progressive pages, or record why the REST list stays. Since #355 and #424, background prefetch also reads these lists for rows in view, so the discarded payload is spent more often. Current behavior is correct.

## Notes

Payload audit at ea771741: ordinary file lists and diffs already come from Git when the store has exact endpoints. Only the unattached/truncated fallback downloads the REST file-list payload. A50-file public sample was378998decoded bytes, including331757bytes of discarded patch text; a minimal GraphQL equivalent was5605bytes but omits previous filenames for renames. A staged GraphQL/REST hybrid would lose progressive publication and add duplicate requests on rename cases. Preserve correct current behavior; this remains a Low optimization follow-up outside catalog delivery mb-m13a. No patch-free fallback implementation is claimed. Audit evidence is catalog-payload-ea771741/metrics.json and design-audit.json; no private repository or checkout content was used.
