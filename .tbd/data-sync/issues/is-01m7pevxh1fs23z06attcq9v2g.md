---
type: is
id: is-01m7pevxh1fs23z06attcq9v2g
title: "PR view summaries: a deleted file's ink reads dark blue; it should be a darker red, matching the darker green and yellow of added and modified"
kind: bug
status: closed
priority: 2
version: 3
delegate: claude-code@spud10
labels: []
dependencies: []
parent_id: is-01m7ksbn803jhw15qjc6beg7qf
hold: null
hold_until: null
created_at: 2026-11-18T04:33:00.448Z
updated_at: 2026-11-18T04:55:06.526Z
started_at: 2026-11-18T04:34:00.529Z
closed_at: 2026-11-18T04:55:06.525Z
close_reason: "Fixed in PR #555 (fd14a0cf4): the light theme's deleted ink, oklch(50% 0.12 27.2), held 59% of sRGB's chroma at its lightness and hue and read as a dull maroon; it is now oklch(50% 0.19 27.2), 93%, as the dark ink is; hue stays --status-error's 27.2. test_deleted_ink_is_a_red_that_reads_red pins hue, chroma share, and 4.5:1 on every ground in both themes."
resolution: null
duplicate_of: null
---
Owner, 2026-11-18 in chat: 'in the PR view summaries for files that are darker green, darker yellow, but then the removal/deletions look darker blue, when they should be a darker red'.
