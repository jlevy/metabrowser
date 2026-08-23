---
type: is
id: is-01m0prn0jqgf18nj1s6e23n9k2
title: "PR #72 review R4: regions_non_empty counts sr-only text, so it cannot fail on the hole it guards"
kind: bug
status: open
priority: 2
version: 1
labels: []
dependencies: []
parent_id: is-01m0prm49eb29wxywrqtdck27b
created_at: 2026-08-23T07:34:07.190Z
updated_at: 2026-08-23T07:34:07.190Z
---
probe.js:154,159 uses element.textContent, which includes .sr-only content. #tab-files ships a spinner plus an sr-only 'Loading files…' and passes h>0 && chars>0 while being the 615px hole. README.md:218 promises a hole fails it. Same unfalsifiability the retired skeleton_complete had. Fix: measure visible text, or drop the predicate and rely on frame_missing_px.
