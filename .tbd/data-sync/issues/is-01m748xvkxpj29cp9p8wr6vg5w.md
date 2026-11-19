---
type: is
id: is-01m748xvkxpj29cp9p8wr6vg5w
title: "Host mode H5: per-root find-or-start lock, so a root has at most one live server"
kind: feature
status: open
priority: 2
version: 7
spec_path: docs/project/specs/active/plan-2026-11-18-host-mode.md
labels: []
dependencies:
  - type: blocks
    target: is-01m748xwwxrrvvnb49fw9ez5ra
parent_id: is-01m748xpx7bjg68tfaf3q4nxmj
created_at: 2026-11-11T03:02:52.796Z
updated_at: 2026-11-19T16:59:16.888Z
---
Host mode plan step H5, its lock (docs/project/specs/active/plan-2026-11-18-host-mode.md, Implementation Plan and Discovery; Decision HM-1 A, taken 2026-11-19). Discovery, which the lock reads to find a server, is mb-baee (H3).

Delivers: a per-root lock that serializes "find this root's server, else start one", so a root has at most one live server; --present's browser delivery (mb-idri) and a host's start both take it. A test races two starts for one root under it.

Slot: after H3; in Ordering 2, the later V slice after V7.

## Notes

2026-11-19: restructured under host mode plan HM-1 A (docs/project/specs/active/plan-2026-11-18-host-mode.md). Previously titled "Live-server registry with a per-root find-or-start lock", described as "Phase 3. One owner-only state file per live process listing its roots, URL, owner, version, and boot id; readers drop dead pids and failed identity probes; a per-root lock serializes find-or-start so a root has at most one live server. A listing mode with --json and a golden against a fixture runtime directory." Discovery (the state files, the liveness probes, and the listing mode) moved to mb-baee (H3); this bead keeps the find-or-start lock (H5). Dependencies: no longer blocked by mb-qzny; now blocked by mb-baee; mb-9lf4 now waits on mb-baee, the registry it reads, in place of this bead; it still blocks mb-idri.
