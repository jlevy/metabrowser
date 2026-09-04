---
type: is
id: is-01m1mv9zmvtf5nnr5kjs16vq6k
title: "PR #101 R3.3: provider restart is unrecoverable"
kind: task
status: open
priority: 1
version: 1
labels: []
dependencies: []
parent_id: is-01m1mv8fds3d80zj3qmg1cct9b
created_at: 2026-09-03T23:57:44.474Z
updated_at: 2026-09-03T23:57:44.474Z
---
DEFER. Session identity is frozen at open (coordinator.py:73-85); if the change relay fails or merely ends, the coordinator publishes one reset and dies with nothing to restart it (coordinator.py:606-637); open() on the same root is a no-op and close() is terminal. A crashed native engine bricks the inventory plane until server restart. Needs a reopen/supervise path, or the contract must state that provider restart is expressed as reset under an adapter-owned session.
