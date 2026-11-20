---
type: is
id: is-01m7vt8r8h18q4hy0nktf1erxx
title: Print rendered Markdown at KPress quality in Chrome and the app's WebKit
kind: bug
status: in_progress
priority: 1
version: 2
delegate: claude-code@spud10.local
labels: []
dependencies: []
hold: null
hold_until: null
created_at: 2026-11-20T06:28:27.535Z
updated_at: 2026-11-20T06:28:35.334Z
started_at: 2026-11-20T06:28:35.310Z
---
Printing a rendered Markdown document (the print button, Command-P, the app's File > Print) falls short of KPress's print model. WebKit (the macOS app): lazy images below the fold print as nothing; headings strand at a page's foot before a table or figure (no break-after: avoid); @page margin: var() resolves to zero margins. Both engines: <p align=center> prints justified (KPress print sets .kpress p text-align); the print sans (KPress Print Sans) is not loaded when the page prints, so headings print in the variable face's Type3 outlines. Scope: rendered Markdown documents only.
