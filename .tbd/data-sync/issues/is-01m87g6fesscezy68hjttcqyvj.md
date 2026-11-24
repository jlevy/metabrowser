---
type: is
id: is-01m87g6fesscezy68hjttcqyvj
title: Omit redundant navigation on the selected sidebar branch chip
kind: bug
status: closed
priority: 2
version: 7
refs:
  - kind: pr
    url: https://github.com/jlevy/metabrowser/pull/789
    at: 2026-11-24T19:30:06.530Z
  - kind: pr
    url: https://github.com/jlevy/metabrowser/pull/789#pullrequestreview-6045962248
    at: 2026-11-24T19:32:34.501Z
  - kind: other
    url: https://github.com/jlevy/metabrowser/actions/runs/45470743556
    at: 2026-11-24T19:32:34.504Z
  - kind: other
    url: https://github.com/jlevy/metabrowser/actions/runs/45475624122
    at: 2026-11-24T20:03:55.480Z
delegate: codex@spud10.local
labels: []
dependencies: []
parent_id: is-01m7wys615s2mfvbc93c9g2pac
hold: null
hold_until: null
created_at: 2026-11-24T19:23:20.396Z
updated_at: 2026-11-24T20:03:57.016Z
started_at: 2026-11-24T19:24:32.999Z
closed_at: 2026-11-24T20:03:57.015Z
close_reason: "Merged in #789 after independent review and exact make verify. Main CI passed. Installed Chrome confirms the current Files chip keeps copy and applicable GitHub actions, the chooser still opens the committed snapshot, and history menus navigate."
resolution: null
duplicate_of: null
---
The branch or tag chip beside the revision chooser names the source already being viewed. Its own menu should offer copy and the corresponding external link when available, and omit View this branch or tag in that context. The adjacent chooser and other branch menus should still offer navigation to other targets.

## Notes

PR #789 head c0cb5cf19 and independent review are complete. Only the current Files chip omits in-app navigation while retaining copy and applicable GitHub provenance. The checkout Chrome fixture covers using the chooser to open the checked-out branch snapshot and using a history ref menu to navigate. The combined local suite passed 221 checks, and the startup budget still passes at 225,777 compressed bytes. Hosted standard CI and exact make verify are running.
