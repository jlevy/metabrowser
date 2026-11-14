---
type: is
id: is-01m7bjenx1pbfwp8jhp1d3sg88
title: Shutdown logs an InventoryClosedError traceback from the file watcher
kind: bug
status: closed
priority: 3
version: 3
labels: []
dependencies: []
created_at: 2026-11-13T23:04:02.208Z
updated_at: 2026-11-13T23:38:25.206Z
closed_at: 2026-11-13T23:38:25.204Z
close_reason: "Merged in #411: the watcher's last batch is applied through an internal refresh before the inventory closes, and run_watcher waits with asyncio.wait, so shutdown logs no traceback; tests pin the race and that the batch is applied."
resolution: null
duplicate_of: null
---
Seen in a native-app window's server log at shutdown (2026-11-13): "InventoryClosedError exception in shielded future" from task `metabrowser-watchfiles-consumer` (`watch_backends.py` `consume_watch_stream` -> `_emit_batch` -> `python_inventory.py` `refresh` -> `_ensure_open`), followed by "watcher failed while stopping ... mode=native" with a CancelledError chained to the same InventoryClosedError.

The watcher keeps emitting a batch after the inventory handle is closed during shutdown. Done when shutdown stops the watcher before closing the inventory (or treats a closed inventory as a normal stop), with no traceback in the log, and a test pins the order.
