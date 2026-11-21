---
type: is
id: is-01m7xkmrfcwfdjb4g8zs93hxbt
title: Resume the SQLite tables and fsqlite drafts
kind: task
status: closed
priority: 2
version: 5
spec_path: docs/project/specs/active/plan-2026-11-19-tabular-data-and-live-sqlite.md
refs:
  - kind: pr
    url: https://github.com/jlevy/metabrowser/pull/676
    at: 2026-11-20T23:11:10.486Z
  - kind: pr
    url: https://github.com/jlevy/metabrowser/pull/678
    at: 2026-11-20T23:11:10.487Z
delegate: claude-code@spud10.local
labels: []
dependencies: []
parent_id: is-01m7tv7gz4yk6tygqfexgtw0s2
hold: null
hold_until: null
created_at: 2026-11-20T23:11:09.803Z
updated_at: 2026-11-21T11:26:00.589Z
started_at: 2026-11-21T08:35:05.070Z
closed_at: 2026-11-21T11:26:00.589Z
close_reason: "All eight tabular layers landed through #678. Optional fsqlite checks passed the exact local gate, independent hot-journal and installed-package probes, browser live publication, branch workflows, and final main CI and macOS app workflows at 98c2dffd."
resolution: null
duplicate_of: null
---
The saved drafts are in GitHub stack 657. GitHub base order is #649 plugin dependencies, #656 table protocol/CSV, #668 table view, #673 record lists, #674 SQLite access, #675 live tables, #676 SQLite tables, #678 fsqlite stores. Preserve all drafts and update refs by fast-forward only. The cloud Claude session is linked in the commits as session_01E8g3iN44KuoyWNe9T3xmGt. No unpushed local implementation worktree was found.

#676 (mb-i9qr) is at 730d59b995791b6c211676055b91ab8a2274b580, target #675. #675 currently includes #674's doctor golden and free-threaded reader fixes through 32b45b0c3e8eddd4fbea7d651ff3cf61befb29b8. A three-way merge preview from the actual common ancestor at the earlier #675 head found ~45 conflicts. The scope of review A is the delta from 9381e85a5 to 730d59b99. Using that older reviewed layer base in a read-only comparison reduces ~45 collisions to 14 genuinely overlapping files. Use that comparison to resolve a real merge of the current #675 head into #676. Preserve #675's lower-layer behavior, then apply the #676 SQLite manifest, sidekick, views/routes and docs/golden additions. #676's temporary deny_reads copy must use the implementation already supplied by the current #674. Verify both old #676 and latest #675 are ancestors and compare the final #675-to-merge diff against the reviewed phase delta.

#676 review A was pinned at a92251faa. Two later saved commits address several findings, including the virtual-table policy in A1. Recheck their behavior on the merged result. A2 (bounded queries that return no matches and cannot continue) and remaining medium findings need explicit dispositions before this draft is ready. In the resolved checkout run the focused SQLite access, guest, pin, table and browserless session tests plus live file-watch tests. Refresh the SQLite, plugin, doctor, and table goldens against actual output. Run make lint-check and make verify, then check GitHub CI on the exact head.

#678 (mb-zzxf) is at e62226463a2dcfbc0daceb9a0de683f85192ca11 and directly targets #676. Its current head contains a92251faa, two commits behind the saved #676 head. After #676 is integrated and checked, merge it into #678 by fast-forwarding the draft ref to a merge commit. Verify fsqlite read-only snapshot behavior and run tests/test_fsqlite_store.py, its CLI and browserless goldens, the packaged-wheel plugin smoke, and the focused real-browser view check. Its current CI used the older lower-layer benchmark and plugin set. It still needs its first senior review.

Concrete local blocker on 2026-11-20: /Volumes/spud-ext2 was absent, so the required scratch workspace, dependency setup, golden regeneration and full local verification cannot run on this Mac. Fetching and the read-only merge preview succeeded. A Linux or macOS environment with approved scratch can resume the resolved checkout. No unreviewed high-conflict API edit or landing was attempted.

## Notes

External scratch was mounted and verified writable on 2026-11-21. The verified #676 merge and review follow-ups are committed on codex/metab-sqlite-676-recovery at 3cbc7b8624942020d4dfc1f760686c34bca725d5. #678 recovery is assigned separately against this base. Keep this task open until both workstreams finish their PR gates.
