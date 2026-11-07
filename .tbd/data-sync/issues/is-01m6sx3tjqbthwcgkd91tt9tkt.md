---
type: is
id: is-01m6sx3tjqbthwcgkd91tt9tkt
title: Share watched-file arrival conventions with GitHub catalog updates
kind: feature
status: in_progress
priority: 2
version: 4
spec_path: docs/project/specs/active/plan-2026-10-01-github-pulls-tab.md
delegate: codex@spud10.local
labels: []
dependencies:
  - type: blocks
    target: is-01m6sx9vy43qz7syctdkmhf455
parent_id: is-01m6f3n89kn7ztmfhrzswxnsgz
hold: null
hold_until: null
created_at: 2026-11-07T02:24:01.110Z
updated_at: 2026-11-07T02:27:19.107Z
started_at: 2026-11-07T02:26:48.159Z
---
Reuse the existing watched-file row arrival and live-update conventions for newly discovered pull requests and future GitHub-backed collections. Preserve row identity, focus, selection, and scroll anchor. Distinguish provider discoveries from initial load, older paging, and filter changes. Keep retries and connection copy in their existing single status, respect reduced motion, and test bounded visible changes in checkout and managed previews.

## Notes

Existing file watcher uses a neutral initial baseline and a reduced-motion-aware pale row flash for real arrivals. Pulls already reconciles numbered rows and preserves focus/scroll. Shared arrival presentation and a settled top-read classification are being added in a separate layer while #312–#315 verification continues.
