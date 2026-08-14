---
type: is
id: is-01m00gvj4chkzdbx9kr8xv7nsd
title: Forbid speculative compatibility layers and remove the file-type compat layer
kind: chore
status: open
priority: 1
version: 1
labels: []
dependencies: []
created_at: 2026-08-14T16:14:35.660Z
updated_at: 2026-08-14T16:14:35.660Z
---
Add a Compatibility and Legacy Code rule to docs/development.md and AGENTS.md: no alias, fallback, shim, deprecation window, or transitional duplicate field without a consumer that cannot be updated in the same commit. Metabrowser serves an uncached page with content-versioned asset URLs and inlined settings, so server/browser version skew is impossible and code guarding against it is unreachable.

Remove the layer that motivated the rule: type_tallies, the type_top alias, ROLLUP_FILE_TYPE_NAMED_LIMIT/RAW_LIMIT, serialize_file_type_taxonomy, the categories/categoryForFile SDK aliases, and the unreachable ext_tallies treemap fallback.

Also add a Changing This Guidance rule (state the reason, prefer a check to a sentence, no unmaintained numbers in prose, delete rules whose reason lapsed) and remove three stale baselines from docs/development.md that had drifted badly while the same work stayed tracked in mb-hmwo, mb-ffo9, and mb-q1wo.
