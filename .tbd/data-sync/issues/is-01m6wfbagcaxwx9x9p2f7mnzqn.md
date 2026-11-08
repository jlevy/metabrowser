---
type: is
id: is-01m6wfbagcaxwx9x9p2f7mnzqn
title: Materialize linked dependency roots in the release benchmark corpus
kind: bug
status: in_progress
priority: 1
version: 2
spec_path: docs/project/specs/active/plan-2026-09-23-v012-thin-mirror.md
delegate: codex@spud10
labels: []
dependencies: []
parent_id: is-01m3wjge2pn6nf3cvcvpbbdx2z
hold: null
hold_until: null
created_at: 2026-11-08T02:21:10.027Z
updated_at: 2026-11-08T02:50:40.356Z
started_at: 2026-11-08T02:50:40.349Z
---
Verified preparation issue on this Mac: build_project_corpus uses cp -c -R on REPO/node_modules and REPO/.venv, which are external-storage symlinks in the active checkout. BSD cp succeeds by copying each symlink, so os.walk of the containing corpus sees zero dependency contents instead of the installed tree. A one-file APFS probe confirms it; walking the symlink as a root sees one file, while walking the containing corpus sees zero. Before release performance comparisons, resolve source roots (or equivalently materialize their contents), invalidate stale malformed corpus markers as needed, and add a tiny behavioral regression with linked install roots. Keep the same frozen representative corpus across both installed-wheel conditions. This is benchmark preparation, not an application regression or reason to rewrite the already reviewed feature stack.
