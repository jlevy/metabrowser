---
type: is
id: is-01m6frzhg6207j9m3thprk45yn
title: Share the diff plugin's kept manifest with the changed-files list
kind: task
status: open
priority: 3
version: 6
spec_path: docs/project/specs/done/plan-2026-10-01-github-pulls-tab.md
labels: []
dependencies: []
parent_id: is-01m6f39t9zax1nbajkkasya6st
created_at: 2026-11-03T03:59:22.118Z
updated_at: 2026-11-25T02:39:23.094Z
---
The changed-files job computes a local comparison's manifest itself: _from_comparison in builtin_plugins/github/pull_files_refresh.py calls GitDiffSource.manifest directly (0.26 s on django/django#15387 at 2,000 files; exp-040 measured 1.16 s on a 1,183-file PR), then caches the list in <n>.files.json. Changes keeps the same manifest: since #348 the comparison route and pull_rendered_diff.py read it through shared_pull_manifest in pull_manifest.py, which goes through the diff plugin's shared_comparison_manifest (_COMPARISONS, keyed by comparison_cache_key with the store tag) and the on-disk manifest bank. Route _from_comparison through shared_pull_manifest so Git lists each comparison once, and test both directions: the list hits an entry Changes kept, and Changes hits an entry the list computed. The list resolves base_policy direct on the record's merge base while shared_pull_manifest asks merge_base, so check that keys and resolved endpoints agree before sharing. MAX_MANIFEST_FILES (2,000, diff/adapters/git.py) stays below GitHub's 3,000, so lists of 2,001 to 3,000 files fall back to GitHub's (mb-ivvw holds raising it).

## Notes

2026-11-03 HANDOFF: not started in this half (see mb-q3jt for where the step stands).

2026-11-03, from the diff plugin's owner: step 4 may add a small public accessor in builtin_plugins/diff/ that reads through the same kept comparison (_COMPARISONS). Conditions, from bugs #284's reviews found: (1) build its key with the cache's own key function, never a second spelling; the key includes the store tag (git dir plus info/attributes) and the read policy, since a key without the store tag served a stale body after an info/attributes edit. (2) The manifest computed for the list must be the one the comparison would keep, so the list and Files changed never disagree; test both directions (the accessor hits an entry the route kept, and the route hits an entry the accessor computed). No route form; note the accessor in the arch map's diff paragraph. MAX_MANIFEST_FILES stays 2,000 for this release (mb-ivvw holds raising it with the batched mount); falling through to GitHub's list for 2,001-3,000 files is fine, and Files changed's note must say the list is cut (listTruncated). Do this in step 4's second half, after the overlay head is merged into pulls-4.
