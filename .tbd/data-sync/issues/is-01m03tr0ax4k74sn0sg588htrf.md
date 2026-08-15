---
type: is
id: is-01m03tr0ax4k74sn0sg588htrf
title: Hide README table of contents when rendered in the folder Overview tab
kind: task
status: open
priority: 2
version: 1
labels: []
dependencies: []
parent_id: is-01m03tqjzm7j6qkxjeath5qe0d
created_at: 2026-08-15T23:05:08.188Z
updated_at: 2026-08-15T23:05:08.188Z
---
The folder Overview tab embeds the README when present. For longer READMEs the Markdown renderer also shows a table of contents alongside the content. Inside the Overview tab the TOC does not make sense; suppress it there. Direct rendering of any Markdown doc (including the README viewed as a file) keeps the usual TOC logic.
