---
type: is
id: is-01m6f3a9djmnfvp42fmnwhwtr7
title: "PullFileList: job, routes, and bounds"
kind: task
status: open
priority: 1
version: 3
spec_path: docs/project/specs/active/plan-2026-10-01-github-pulls-tab.md
labels: []
dependencies:
  - type: blocks
    target: is-01m6f3a9tmf2t5m4pcb97gfr0j
parent_id: is-01m6f39zpnk9rc3kjy552b88qj
created_at: 2026-11-02T21:40:45.617Z
updated_at: 2026-11-02T22:39:28.716Z
---
One gh request per 100 files, the patch dropped, a cut list said honestly, freshness from the row's updated_at, GET pull-files and POST pull-files-refresh, and goldens. Needs no Git, proven on a source with no store.

## Notes

2026-11-02: design correction to apply in this bead and the plan, from exp-040. gh api pulls/<n>/files is one small read only for small pull requests: 12 pages at 1.2-1.6 s each, about 15-20 s, on the 1,183-file one. So read it progressively, publishing each page to the tree as it arrives, with an honest N of M while it fills (M from the pull request's changed_files where the record has it, or from the Link header's last page otherwise), and cache it. When the mirror already has the head, use the local comparison manifest instead, which is far faster and needs no network; the gh list is for a pull request whose commits are not local. A rename's new path is the row's identity either way, because scrollToFile takes a path. The tree must meet the budgets on mb-zx9q at that size.
