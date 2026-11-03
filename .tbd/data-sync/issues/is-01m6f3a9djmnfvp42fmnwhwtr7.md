---
type: is
id: is-01m6f3a9djmnfvp42fmnwhwtr7
title: "PullFileList: job, routes, and bounds"
kind: task
status: in_progress
priority: 1
version: 8
spec_path: docs/project/specs/active/plan-2026-10-01-github-pulls-tab.md
delegate: claude-code@spud10
labels: []
dependencies:
  - type: blocks
    target: is-01m6f3a9tmf2t5m4pcb97gfr0j
parent_id: is-01m6f39zpnk9rc3kjy552b88qj
child_order_hints:
  - is-01m6frzh3stte4sry5t7zqrvrr
  - is-01m6frzhg6207j9m3thprk45yn
hold: null
hold_until: null
created_at: 2026-11-02T21:40:45.617Z
updated_at: 2026-11-03T04:31:40.359Z
started_at: 2026-11-03T03:58:48.242Z
---
One gh request per 100 files, the patch dropped, a cut list said honestly, freshness from the row's updated_at, GET pull-files and POST pull-files-refresh, and goldens. Needs no Git, proven on a source with no store.

## Notes

2026-11-02: design correction to apply in this bead and the plan, from exp-040. gh api pulls/<n>/files is one small read only for small pull requests: 12 pages at 1.2-1.6 s each, about 15-20 s, on the 1,183-file one. So read it progressively, publishing each page to the tree as it arrives, with an honest N of M while it fills (M from the pull request's changed_files where the record has it, or from the Link header's last page otherwise), and cache it. When the mirror already has the head, use the local comparison manifest instead, which is far faster and needs no network; the gh list is for a pull request whose commits are not local. A rename's new path is the row's identity either way, because scrollToFile takes a path. The tree must meet the budgets on mb-zx9q at that size.

2026-11-03: done on claude/pulls-4-files (commits 4990b1e0, 1cad4c5a). PullFileList in pull_list.py, refresh_pull_files in pull_files_refresh.py, routes in pull_files_route.py and sidekick.py (GET pull-files with offset/limit windows and an ETag; POST pull-files-refresh with number/retry). Local comparison through GitDiffSource.manifest (no patch, no network) when the record's comparison is in the served store and the manifest is not cut at MAX_MANIFEST_FILES; otherwise GitHub's pages, published one by one, never as fewer pages than the file holds. Freshness: comparison list current while the record head is its head; GitHub list current while updated_at (record or cached list row) <= fetched_at, else the window. Job: network=False, a coordinator slot per gh request, MAX_PULL_JOBS bound, 429 too_many. Measured: nodejs/node#65161 (GitHub's 3,000 cap; page 30 has no next link) 30 pages, 27.0 s job, file 378 KB; django/django#15387 2,003 files 21 pages 17.2 s, local manifest 0.26 s but cut at 2,000; worst file 6.38 MB under the 8 MiB bound. N of M from the record is NOT done: the record has no changed_files (see the follow-up bead); the count is N files and pages read of the Link's last page.


2026-11-03 (later): 7de06f9d weighs a partial list by rows, so a comparison list is never replaced by GitHub page 1. Against #284 (f7cf3464): the local source already calls the manifest half of the split, GitDiffSource.resolve and .manifest on a store GitLocation, whose signatures are unchanged there and whose store reads inherit STORE_READ_POLICY attribute isolation; direct policy on the record merge base, so no base_uncertain; any DiffSourceError/GitError (commits_unavailable, lender_missing) falls through to GitHub. Not shared: the diff plugin private _COMPARISONS cache (mb-w5rc). Branch head a84968ab, make test passed.
