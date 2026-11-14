---
type: is
id: is-01m7bb81c0fx9ycnaqjgf95qt5
title: "Overview page: File Overview and Readme toggles share one left edge at every width"
kind: bug
status: closed
priority: 2
version: 3
labels: []
dependencies: []
created_at: 2026-11-13T20:58:04.543Z
updated_at: 2026-11-13T21:44:39.705Z
closed_at: 2026-11-13T21:44:39.704Z
close_reason: "Merged in #405: the Overview's section labels share one inset, the tab bar's (--file-tab-padding-x), at every width; a headless-Chrome test pins it at 900 to 2560 px."
resolution: null
duplicate_of: null
---
The user (2026-11-13): "on the Overview page, the toggles for File Overview and Readme are styled correctly but the text of the toggle is indented different amounts at larger screen widths on desktop. let's keep it left aligned in a consistent way"

Done when: on a folder's Overview, the File Overview and Readme toggle labels share one left edge at every width, measured in Chrome from narrow to wide desktop (for example 900 to 2560 px), with a test that pins it, and the design system states the rule.
