---
type: is
id: is-01m744rtrz3b4h8jhz65t8mh1x
title: Activity tracker polls every .logs/.state file every 5 s, costing 11-17% of a core while idle
kind: bug
status: open
priority: 2
version: 1
labels: []
dependencies: []
created_at: 2026-11-11T01:50:13.790Z
updated_at: 2026-11-11T01:50:13.790Z
---
Measured on 0.12.0 (M1 Pro, macOS 26.5.2): a server that has finished walking keeps using 11-17% of one core indefinitely on trees with 31-35k trackable files under .logs/.state (0.77% on a 36k-entry tree with none; 0.2-0.4% on ordinary folders). Each ACTIVE_TRACKER_INTERVAL_S (5 s) tick in src/metabrowser/active_tracker.py reads every trackable catalog record under the scoped dirs (max_rows = budget max_files) and polls each path. Correlation measured, cause read from code, not profiled. It makes warm servers expensive on log-heavy folders, which matters for the native app's warm-folder policy (research-2026-11-10-native-app-server-topology.md). Likely fixes: poll only recently changed candidates (FSEvents already reports changes), cap or rotate the candidate set, or back off when nothing changed.
