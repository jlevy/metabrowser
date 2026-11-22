---
type: is
id: is-01m82s9dazkkwgfnqzq839p031
title: "PR #709 K7: an answer slower than 5 s makes the page ask again at once"
kind: bug
status: closed
priority: 2
version: 2
spec_path: docs/project/specs/active/plan-2026-11-22-pull-request-update-cadence.md
labels: []
dependencies: []
parent_id: is-01m82s73za15hfvfw96fdn9e19
created_at: 2026-11-22T23:26:01.558Z
updated_at: 2026-11-22T23:45:40.579Z
closed_at: 2026-11-22T23:45:40.572Z
close_reason: "fixed in aebc9cbb9: PROBE_ASK_GAP_MS 1 s after the last answer; page-session step pins it"
resolution: null
duplicate_of: null
---
Suggestion. pull-page.js automaticAskWait. https://github.com/jlevy/metabrowser/pull/709#pullrequestreview-6015081008
