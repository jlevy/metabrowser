---
type: is
id: is-01m85nhkkpfmbb0cyj943eyh1g
title: Prose faces documents test shares one 30 s deadline between the server's start and the Chrome session, set from one 5.4 s run at load 7, so under contention a slow start takes the session's time
kind: bug
status: closed
priority: 2
version: 3
refs:
  - kind: pr
    url: https://github.com/jlevy/metabrowser/pull/781
    at: 2026-11-24T02:20:31.939Z
labels: []
dependencies: []
created_at: 2026-11-24T02:18:19.125Z
updated_at: 2026-11-24T02:20:32.828Z
closed_at: 2026-11-24T02:20:32.827Z
close_reason: "One 30 s deadline, set from a single 5.4 s run at load 7, covered both the server's start and the Chrome session, so contention took the session's time; nothing stalled. Six at once at load 105-180 the session took 27.6-28.6 s and 5 of 6 whole runs passed 30 s. The start keeps SERVER_START_TIMEOUT_S; the session gets a measured 90 s from the Serving line, in PR #781 (open, not merged). Sibling tests/test_staged_fonts_chrome.py shares a deadline the same way and is unchanged."
resolution: null
duplicate_of: null
---
tests/test_prose_faces_chrome.py::test_documents_read_in_the_reading_font_and_chrome_prose_in_sans set deadline = now + RUN_BUDGET_S (30) before starting metab, bounded the start by min(deadline, now + SERVER_START_TIMEOUT_S 20), and gave the session whatever remained. The comment recorded a single run: 5.4 s whole, session 2.5 s, at a load average of 7. Reported (serif-audit, PR #777): at load ~400 beside two other Chrome sessions the session reached 6 of its 12 pages, 1.1-4.2 s each, inside the 30 s; 14.4 s alone. Measured on a 10-core Mac 2026-11-23 (attic/prose_measure.py): alone at load ~95, server start 2.0-4.8 s, session 8.1-9.9 s; six at once, load 105 to 180, session 27.6-28.6 s (Chrome start 4.3-4.8 s, 12 pages 0.3-4.6 s each, 16.4-17.8 s in all), and 5 of 6 whole runs over 30 s. Nothing stalled: every page answered, slower in proportion to contention. Sibling with the same shared-deadline pattern, not changed here: tests/test_staged_fonts_chrome.py (RUN_BUDGET_S 30 shared with SERVER_START_TIMEOUT_S 20).
