---
type: is
id: is-01m7wysrh5ggf7dm4xvqm8dmmp
title: "Host mode: a root's server that the CLI, agents, and the app can find, reach, and reuse"
kind: epic
status: open
priority: 2
version: 1
spec_path: docs/project/specs/active/plan-2026-11-10-native-macos-app.md
labels: []
dependencies: []
parent_id: is-01m748xpx7bjg68tfaf3q4nxmj
created_at: 2026-11-20T17:06:53.604Z
updated_at: 2026-11-20T17:06:53.604Z
---
Plan: docs/project/specs/active/plan-2026-11-18-host-mode.md, in the open plan PR #570 (steps H1 to H9). A root has at most one live server that the CLI, an agent and the macOS app can find, reach and reuse: a ready moment, a boot ID and process fields on /api/identity (H1, mb-hhzd); the server record and ready-line flag (H2, mb-wpel); discovery, liveness probes and a listing mode (H3, mb-baee); metab ROOT --api ROUTE --live (H4, mb-77x9); idle exit and the per-root find-or-start lock (H5, mb-k3yz, mb-5xi4); a sticky port per root (H6, mb-e74k); control verbs on an owner-only socket (H7, mb-1zyp); the per-launch token and gates (H8, mb-qzny); and the app's link scheme, rendezvous and attach (H9, mb-rtgh).

Also the page following navigate events (mb-54r1) and the agent front door beyond the release slice in mb-jl8o (mb-idri). No step is built yet: nothing on main reads a boot ID, a registry, --live, idle exit or a find-or-start lock.
