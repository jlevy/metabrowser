---
type: is
id: is-01m82jg3mpy9q29kj10j58qqyv
title: "Main Chrome CI: prose font probe loses the commit body"
kind: bug
status: in_progress
priority: 1
version: 2
delegate: codex@spud10
labels: []
dependencies: []
parent_id: is-01m7hgpc9550w78kmwqsvv64xh
hold: null
hold_until: null
created_at: 2026-11-22T21:27:20.956Z
updated_at: 2026-11-22T21:28:15.500Z
started_at: 2026-11-22T21:28:15.498Z
---
Main CI run 45070667844 at 472108123b78e8db9a4c5e321489dc8264c590b2 failed on Python 3.14t in tests/test_prose_faces_chrome.py. The DOM probe found the commit body before font lookup, then reported that the text left the page. Diagnose whether commit refresh replaces an instrumented node or the page is missing expected content. Keep the drawn-font assertion and distinguish this failure from the previously tracked missing CDP node error.
