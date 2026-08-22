---
type: is
id: is-01m0k5xg6xhbr1tp13ypkr40fh
title: Attribute CLI start-to-serving and remove the part that scales with the tree
kind: task
status: open
priority: 1
version: 4
spec_path: docs/project/specs/active/plan-2026-08-21-load-time-performance.md
labels: []
dependencies: []
parent_id: is-01m0k5wh7jgr0dgs5y78kwwke1
created_at: 2026-08-21T22:08:59.101Z
updated_at: 2026-08-22T06:10:44.439Z
---
Attribute CLI start-to-serving before changing it. First numbers are in (H17, plan Backlog):

python -X importtime -c "import metabrowser.server" costs 390-770 ms on this machine (varies with page cache), before any walk. Dominant shares: kpress ~74 ms, plugin_loader.manifest + pydantic model construction ~60 ms, plugin_api ~45 ms, classify ~57 ms, inventory ~38 ms, activity ~30 ms. discover_plugins also runs at module scope (server.py, _DISCOVERY), so plugin discovery and manifest validation are paid at import time.

The plan's earlier "113 ms module import" undercounts here by 3-6x. Remaining work: separate interpreter start / import / discovery / bind in bench_serving's start-to-serving phase, then defer what only serving needs (kpress, plugin discovery) as its own experiment through the explorations loop.

Ordered after H8 (mb-vki5): a client that waits ~1.5 s on the nav-tally pass makes every server cost look like scan cost.
