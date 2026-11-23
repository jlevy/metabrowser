---
type: is
id: is-01m859498cg0bxa4ytprh2sy0y
title: Bound first clones by the cache volume's free space, not a fixed size
kind: task
status: in_progress
priority: 2
version: 3
delegate: claude-code@vm
labels: []
dependencies: []
parent_id: is-01m6f3n89kn7ztmfhrzswxnsgz
hold: null
hold_until: null
created_at: 2026-11-23T22:41:19.628Z
updated_at: 2026-11-23T22:41:40.001Z
started_at: 2026-11-23T22:41:26.145Z
---
A first clone of a GitHub repository is refused over MAX_FIRST_CLONE_KB (1,350,000 KB), a stand-in for the 900 s acquisition deadline. Replace it with a free-space check: refuse when the reported size, packed at 1.1x, would leave less than a reserve (1 GB, METABROWSER_CACHE_RESERVE_MB) free on the cache's volume. The doctor's low-free-space warning follows the same reserve. Logic stays in metab; the app only shows its message.
