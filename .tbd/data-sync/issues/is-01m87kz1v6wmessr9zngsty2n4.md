---
type: is
id: is-01m87kz1v6wmessr9zngsty2n4
title: "Guided review: an out-of-date guide is a one-line warning with a remedy, and keeps working"
kind: bug
status: in_progress
priority: 1
version: 2
delegate: claude-code@spud10.local
labels: []
dependencies: []
parent_id: is-01m87ky2a36j5yg4pf9827xxd6
hold: null
hold_until: null
created_at: 2026-11-24T20:29:11.396Z
updated_at: 2026-11-24T20:38:44.178Z
started_at: 2026-11-24T20:38:44.176Z
---
guided-review.js (around :360) renders the stale notice with commit lists, SHAs, merge-base and rebase talk, and changed file paths. Replace with one warning line and one remedy (the author re-pins the guide), keep showing the steps, and mark only the affected steps subtly. Keep the details in the guided-review route's JSON. Update the session, mount checks, goldens, and docs.
