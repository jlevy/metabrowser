---
type: is
id: is-01m74t2mt0hfp93byfz32b6f6t
title: "PR #346 A2: Retry changes and 'could not be fetched' appear before any attempt"
kind: bug
status: closed
priority: 2
version: 3
delegate: claude-code@spud10.local
labels: []
dependencies: []
parent_id: is-01m74t21pvwps4wh189z73rspr
hold: null
hold_until: null
created_at: 2026-11-11T08:02:35.455Z
updated_at: 2026-11-11T08:21:19.704Z
started_at: 2026-11-11T08:02:46.851Z
closed_at: 2026-11-11T08:21:19.703Z
close_reason: "Fixed in 9c625f4e: canRetryComparison only after an attempt or a held outcome; a failed read before any attempt shows 'Changes have not been fetched.' with no action and the next good read asks. Confirmed by github-pull-manual-refresh-behavior.js (failed on 63d5d7f) and the session's read-error steps."
resolution: null
duplicate_of: null
---
Low. pull-page.js:940-941 sets canRetryComparison = !changesPending, so a failed GET or refused metadata Refresh offers Retry with no attempt. Fix: canRetryComparison only after an attempt; neutral text for an unattempted page with a read error. Review: https://github.com/jlevy/metabrowser/pull/346#pullrequestreview-5855482052 (PR #346, review A, round 1).
