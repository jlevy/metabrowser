---
type: is
id: is-01m0hj5ass469axrp70tta93j9
title: "Test filtering from the CLI: walk filter flags, goldens, check-api step"
kind: task
status: open
priority: 1
version: 1
labels: []
dependencies: []
parent_id: is-01m0hhjf2e1w8tp30ay4tj8183
created_at: 2026-08-21T07:04:29.752Z
updated_at: 2026-08-21T07:04:29.752Z
---
Make the filter answerable from the command line, so folder, filter, and rollup logic is tested as data rather than by looking at a browser.

Three surfaces, cheapest first:

1. Walk mode. `metab ROOT --walk --format json` already dumps the exact envelope the nav panel consumes. Give it the same filter vocabulary the nav bar uses (type, age, minimum size, include-ignored) and the whole question becomes a diffable transcript: which folders survive, what each folder rolls up to, how many files matched. Cover it in tests/golden/cli-walk.tryscript.md against the pinned fixture tree, which already has deterministic sizes and mtimes.

2. Route-level pytest over the filtered projection: bottom-up rollups, pruning of non-matching subtrees, gitignored handling, and the depth cap.

3. `metab --check-api`, which drives the real ASGI stack in-process with no port and no browser. Add a filtered step to the nav scenario so the CLI transcript covers the filtered route the way it covers the plain one.

What is left for the browser after this is only what is genuinely visual: the disclosure motion, the selection box, and focus.
