---
type: is
id: is-01m6wfbagcaxwx9x9p2f7mnzqn
title: Materialize linked dependency roots in the release benchmark corpus
kind: bug
status: closed
priority: 1
version: 4
spec_path: docs/project/specs/active/plan-2026-09-23-v012-thin-mirror.md
delegate: codex@spud10
labels: []
dependencies: []
parent_id: is-01m3wjge2pn6nf3cvcvpbbdx2z
hold: null
hold_until: null
created_at: 2026-11-08T02:21:10.027Z
updated_at: 2026-11-08T05:15:33.741Z
started_at: 2026-11-08T02:50:40.349Z
closed_at: 2026-11-08T05:15:33.741Z
close_reason: Merged through native stack331 (#328–#330) at d33550455d1a44bb275d5e71492f9bdbc682f0c5. The landed tree exactly equals reviewed/gated519c33239. Independent senior review is complete for each layer; UI also has dedicated security/performance passes. All nine checks passed on every exact PR head; full local make verify passed4917 tests/9 expected skips and385 goldens, audits/types/distribution. The exact gated wheel is installed under both aliases, all11 plugins and30 served assets verified, with both repository-mode PR tabs, positional menus, narrow fit, typography and Reload keyboard acceptance. Corpus linked-root regression also passes; separate release gates and final documentation wording remain open.
resolution: null
duplicate_of: null
---
Verified preparation issue on this Mac: build_project_corpus uses cp -c -R on REPO/node_modules and REPO/.venv, which are external-storage symlinks in the active checkout. BSD cp succeeds by copying each symlink, so os.walk of the containing corpus sees zero dependency contents instead of the installed tree. A one-file APFS probe confirms it; walking the symlink as a root sees one file, while walking the containing corpus sees zero. Before release performance comparisons, resolve source roots (or equivalently materialize their contents), invalidate stale malformed corpus markers as needed, and add a tiny behavioral regression with linked install roots. Keep the same frozen representative corpus across both installed-wheel conditions. This is benchmark preparation, not an application regression or reason to rewrite the already reviewed feature stack.

## Notes

November 7 release-preparation checkpoint: Correction implemented on release-preparation branch: resolve each copy source root before BSD cp and bump project-corpus shape to2 so old markers rebuild. Behavioral regression exercises both fresh and shape1-marked corpora with externally linked node_modules/.venv and independently walks the copied tree. Fails prior code in0.14s, all26 serving-harness tests pass in2.61s after fix. Full lint/format checks pass. Cross-volume clone probe succeeded, so no speculative partial-copy cleanup or unrelated fallback change was added. Publication/review/CI still pending.
