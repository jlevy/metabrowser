---
type: is
id: is-01m7nfgjv2d783zg23ykdd7kgg
title: "GitHub routes: warm their lazily imported modules at server start, off the event loop"
kind: task
status: open
priority: 2
version: 1
labels: []
dependencies: []
parent_id: is-01m7n6v8n050erzeb13c5tasar
created_at: 2026-11-17T19:25:03.201Z
updated_at: 2026-11-17T19:25:03.201Z
---
Fix 3 from exp-099 (mb-g5wf). A fresh server's first GitHub route answers (GET pull, stacks, pulls) take 350 to 500 ms and finish together, in every build since v0.12.0; repeat calls take 4 to 21 ms. The GitHub route modules' lazy import is about 120 to 150 ms of it.

Probe (2026-11-17, untimed protocol, browserless, attic only): main c6aa02085 against main plus a startup thread that imports pull_route, pull_list_route, pull_stacks_route, pull_files_route, pull_markdown and KPress (local commit scratch/warm-probe 81e1ea217, not pushed). Fresh server on a warm cache, pr-view-first-routes.mjs with a 1 s pause after ready, 4 pairs, load 14: first GET pull 370-410 ms -> 261-291 ms (0.65 / 0.72 / 0.71 / 0.74). Asked at once on ready, while the warm-up still runs: 436-476 -> 405-425 ms (about 6%, load 58-66). About 260 ms of the first GET pull stays unexplained and is worth profiling first.

Not a small change: no plugin startup hook exists. Design to settle: an optional manifest hook (for example a [[warm]] sidekick callable) that the server runs off the event loop after startup; the GitHub plugin's warm checks cheaply that the served source is a GitHub checkout or repository, so browsing a local folder still never loads the cache (sidekick.py docstring). Plugin manifest is an internal contract: change it everywhere in one commit, CHANGELOG note, no PLUGIN_SDK_VERSION bump for an optional field. Measure with the committed pr-view benchmark (pr-warm, pr-store title and pull_ms) under a registered protocol.
