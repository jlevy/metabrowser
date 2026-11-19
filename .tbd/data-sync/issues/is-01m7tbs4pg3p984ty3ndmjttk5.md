---
type: is
id: is-01m7tbs4pg3p984ty3ndmjttk5
title: Main page's focus ring is covered by a pull request's tab bar
kind: bug
status: open
priority: 2
version: 1
labels: []
dependencies: []
created_at: 2026-11-19T16:56:01.486Z
updated_at: 2026-11-19T16:56:01.486Z
---
Owner, 2026-11-19, verbatim: "the border on the main window that indicates focus seems to have a lower z index than some backgrounds, the part of the tabs with the Conversation and Changs section is covering up the blue border indicating focus". Cause: .preview-pane:focus-visible draws an inset outline on the scroller, which paints under its scrolled content.
