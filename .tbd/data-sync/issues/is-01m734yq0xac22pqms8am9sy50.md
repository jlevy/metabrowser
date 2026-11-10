---
type: is
id: is-01m734yq0xac22pqms8am9sy50
title: Compare rendered and Source PR startup on documentation-heavy diffs
kind: task
status: open
priority: 2
version: 3
spec_path: docs/project/specs/active/plan-2026-08-17-general-diff-rendering.md
labels: []
dependencies: []
parent_id: is-01m7327d4wd92r1n5bnmr1b0zb
created_at: 2026-11-10T16:34:12.124Z
updated_at: 2026-11-10T18:29:40.666Z
---
Run a paired built-in browser session on a documentation-heavy comparison in checkout and managed modes. Measure first useful diff content and main-thread work with warm and cold projection caches. Keep it separate from the existing Markdown parser timing and from the release-wide benchmark.

## Notes

Implementation to benchmark: https://github.com/jlevy/metabrowser/pull/349 at 5860c1dd1. Two warm projection samples took 58–72 ms. The paired docs-heavy browser timing remains outstanding.

Current CI-green stack tip for paired browser timing: #349 at 705d85a1c. The rendered and Source comparison in both repository modes is still open.
