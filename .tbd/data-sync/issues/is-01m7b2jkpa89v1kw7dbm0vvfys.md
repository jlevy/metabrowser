---
type: is
id: is-01m7b2jkpa89v1kw7dbm0vvfys
title: Repository identity rediscovery (GIT_REPO_INFO_TTL_S, 5 s) adds about 60 ms to whichever git request pays it
kind: bug
status: closed
priority: 2
version: 3
spec_path: docs/project/specs/active/plan-2026-11-11-ui-apparent-performance.md
labels: []
dependencies: []
parent_id: is-01m774q0ep0jq6vhb790rart0v
created_at: 2026-11-13T18:26:33.801Z
updated_at: 2026-11-14T18:47:45.895Z
closed_at: 2026-11-14T18:47:45.894Z
close_reason: "Fixed in #368 (36d3e325, fc2a6d84; merge c74d0ef3): an owned repository keeps its identity past the 5 s TTL while its refs' state is unchanged and is rediscovered off the request after 60 s, so an interactive request no longer pays the rediscovery (exp-086: TTL-boundary comparison ratio 1.59 to 1.00)."
resolution: null
duplicate_of: null
---
Found by the #368 diagnostic traces (exp-081/082 follow-up, 2026-11-13). With a pull-cores-prepare from the Pulls catalog walk overlapping or answering 50-127 ms before them, /api/plugin/diff/comparison server time rose from 77.6-84.4 ms to 128.3-155.7 ms and the commit detail from 22.4-28.0 ms to 71.7-82.7 ms (Server-Timing srv). That moved commits.hover_click's ready from about 16 ms to 35 ms (one frame) and put commits.cold.1 in its slow mode. Suspected: work the prepare leaves running after it answers (cached_batch in asyncio.to_thread, and whatever follows). A corrected contention sweep (fresh pages through next_after, comparison and commit at 0/100/300 ms after a prepare answers) is written but not yet run. Fix direction: interactive requests first, background preparation yields or is throttled while a reader is navigating.

## Notes

Corrected 2026-11-13 by the #368 contention sweep (run 19:36-19:38Z, rule registered in criteria-exp086.txt before it ran): concurrent catalog prepares do NOT slow git requests (no sweep cell passed). The slow requests are exactly the ones that pay the 5 s repository-identity rediscovery: on both builds the comparisons exp-081's identity-refresh rule marks as refreshes have srv median 140-149 ms against 83-85 ms for the rest. A cache that answers revisits with no git request (#368's comparison cache, the route memo) shifts that refresh onto the next interactive request, such as a hover's comparison. Fix direction: keep the identity fresh while caches serve, or check it as cheaply as the ref-state fingerprint, so no interactive request pays a rediscovery.
