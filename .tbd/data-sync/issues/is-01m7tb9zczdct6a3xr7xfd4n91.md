---
type: is
id: is-01m7tb9zczdct6a3xr7xfd4n91
title: "Host mode H5: idle exit for a detached server"
kind: feature
status: open
priority: 2
version: 2
spec_path: docs/project/specs/active/plan-2026-11-18-host-mode.md
labels: []
dependencies:
  - type: blocks
    target: is-01m748xwwxrrvvnb49fw9ez5ra
parent_id: is-01m748xpx7bjg68tfaf3q4nxmj
created_at: 2026-11-19T16:47:44.542Z
updated_at: 2026-11-19T16:49:47.552Z
---
Host mode plan step H5, its idle-exit part (docs/project/specs/active/plan-2026-11-18-host-mode.md, Implementation Plan and The Host Contract; Decisions HM-1 A and HM-6 A, taken 2026-11-19). Split from mb-qzny.

Delivers: a serve flag under which a server stops after a window, a constant defined and documented in code, with no viewer's event stream held and no request. --present's browser delivery starts its detached server with it (mb-idri), where today that server runs until it is killed (cli/present.py). A golden and the reference-host test.

Slot: in Ordering 2, the later V slice after V7, with the rest of H5.
