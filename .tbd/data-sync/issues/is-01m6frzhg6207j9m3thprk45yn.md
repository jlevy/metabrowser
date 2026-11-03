---
type: is
id: is-01m6frzhg6207j9m3thprk45yn
title: Share the diff plugin's kept manifest with the changed-files list
kind: task
status: open
priority: 3
version: 3
spec_path: docs/project/specs/active/plan-2026-10-01-github-pulls-tab.md
labels: []
dependencies: []
parent_id: is-01m6f3a9djmnfvp42fmnwhwtr7
created_at: 2026-11-03T03:59:22.118Z
updated_at: 2026-11-03T07:19:04.338Z
---
The file-list job computes a local comparison's manifest itself through GitDiffSource.manifest (0.26 s on django/django#15387 at 2,000 files; exp-040 measured 1.16 s on its 1,183-file stress case), once per head, then caches it in <n>.files.json. When Files changed has already asked /api/plugin/diff/comparison for the same endpoints, the diff plugin has computed that manifest too (and on claude/v012-large-pr-perf keeps it in _COMPARISONS). Needed from the diff plugin's owner: a way to read the kept manifest without patches, either a Python function (location, left, right, policy) -> ResolvedManifest that goes through _COMPARISONS, or a manifest-only form of the comparison route. Then the job reads that and Git runs once per comparison. Also: MAX_MANIFEST_FILES (2,000) is below GitHub's 3,000, so pull requests of 2,001-3,000 files fall back to GitHub's list.

## Notes

2026-11-03 HANDOFF: not started in this half (see mb-q3jt for where the step stands).

2026-11-03, from the diff plugin's owner: step 4 may add a small public accessor in builtin_plugins/diff/ that reads through the same kept comparison (_COMPARISONS). Conditions, from bugs #284's reviews found: (1) build its key with the cache's own key function, never a second spelling; the key includes the store tag (git dir plus info/attributes) and the read policy, since a key without the store tag served a stale body after an info/attributes edit. (2) The manifest computed for the list must be the one the comparison would keep, so the list and Files changed never disagree; test both directions (the accessor hits an entry the route kept, and the route hits an entry the accessor computed). No route form; note the accessor in the arch map's diff paragraph. MAX_MANIFEST_FILES stays 2,000 for this release (mb-ivvw holds raising it with the batched mount); falling through to GitHub's list for 2,001-3,000 files is fine, and Files changed's note must say the list is cut (listTruncated). Do this in step 4's second half, after the overlay head is merged into pulls-4.
