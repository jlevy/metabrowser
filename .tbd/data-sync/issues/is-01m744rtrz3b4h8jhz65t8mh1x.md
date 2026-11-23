---
type: is
id: is-01m744rtrz3b4h8jhz65t8mh1x
title: Activity tracker polls every .logs/.state file every 5 s, costing 11-17% of a core while idle
kind: bug
status: closed
priority: 2
version: 6
spec_path: docs/project/specs/active/plan-2026-11-10-native-macos-app.md
delegate: claude-code@spud10.local
labels: []
dependencies:
  - type: blocks
    target: is-01m748xrkn32a8mcak4f8yxy4n
parent_id: is-01m748xpx7bjg68tfaf3q4nxmj
hold: null
hold_until: null
created_at: 2026-11-11T01:50:13.790Z
updated_at: 2026-11-22T23:29:58.907Z
started_at: 2026-11-22T21:03:26.732Z
closed_at: 2026-11-22T23:29:58.903Z
close_reason: "Fixed by #707: idle tick probes active, changed, and a 1,000-file rotating sweep; idle server CPU 29-34% of a core -> 2.1-2.2% on 30,000 files. Tradeoff: an unreported write on >1,000 candidates waits up to one sweep pass (150 s at 30,000)."
resolution: null
duplicate_of: null
---
Measured on 0.12.0 (M1 Pro, macOS 26.5.2): a server that has finished walking keeps using 11-17% of one core indefinitely on trees with 31-35k trackable files under .logs/.state (0.77% on a 36k-entry tree with none; 0.2-0.4% on ordinary folders). Each ACTIVE_TRACKER_INTERVAL_S (5 s) tick in src/metabrowser/active_tracker.py reads every trackable catalog record under the scoped dirs (max_rows = budget max_files) and polls each path. Correlation measured, cause read from code, not profiled. It makes warm servers expensive on log-heavy folders, which matters for the native app's warm-folder policy (research-2026-11-10-native-app-server-topology.md). Likely fixes: poll only recently changed candidates (FSEvents already reports changes), cap or rotate the candidate set, or back off when nothing changed.

## Notes

2026-11-22: PR https://github.com/jlevy/metabrowser/pull/707 (branch claude/active-tracker-idle), open, not merged. Profiled on 30,000 files: about 75% of a tick was the pid lookup made for every .jsonl candidate (glob of its folder, pid file read, signal), about 5% the stat pass, the rest the catalog reread and a patch per record. Fix: reread the candidate set only when the engine version moves; probe the active files, the files whose catalog facts changed, and ACTIVE_TRACKER_SWEEP_FILES (1,000) of a rotating sweep; patch only active files; one pid lookup per folder of active logs. Idle tick CPU, 30,000 files, M1 Pro at load average 240-330: 5.4-7.2 s before and 8-18 ms after (300 folders of 95 logs), 2.1-2.6 s before and 8-9 ms after (3,000 folders of 5). Whole server over 60 s: 29-34% of a core before, 2.1-2.2% after. Latency: unchanged for a write the watcher reports or a folder of at most 1,000 trackable files; a write nothing reports waits one tick per 1,000 candidates (150 s on 30,000). Not verified: the native watcher path end to end (FSEvents delivered nothing on the external volume used), and make verify locally.
