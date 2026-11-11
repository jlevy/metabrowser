---
type: is
id: is-01m75d7rpa48wfg4f0q8c5n4yk
title: "PR #348 F1: the Markdown work estimate charges nothing for lines or paragraphs"
kind: bug
status: closed
priority: 2
version: 3
delegate: claude-code@spud10.local
labels: []
dependencies: []
parent_id: is-01m75d7enb9z11kt1ge773zz3r
hold: null
hold_until: null
created_at: 2026-11-11T13:37:26.217Z
updated_at: 2026-11-11T14:23:39.475Z
started_at: 2026-11-11T13:37:35.988Z
closed_at: 2026-11-11T14:23:39.474Z
close_reason: "Fixed: d52784f7. 26 us per line; \\r and \\r\\n end one line. Grown shapes render 233-413 ms; paragraphs, backslash breaks and the math+paragraph mix are in the costly-shape test."
resolution: null
duplicate_of: null
---
Review F1 (https://github.com/jlevy/metabrowser/pull/348#pullrequestreview-5858785036): 64 KiB of one-character paragraphs estimated 33 ms, rendered 749 ms; with $a$ padding 1,003 ms at an estimate of 400 ms.
