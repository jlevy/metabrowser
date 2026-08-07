---
type: is
id: is-01kzcr8har7zzndq9vtnz0xb1e
title: Bind T as an alias for / to open Quick File
kind: feature
status: closed
priority: 1
version: 2
labels: []
dependencies: []
parent_id: is-01kzcr7qzp4j0x9h694b8evywa
created_at: 2026-08-06T23:59:12.215Z
updated_at: 2026-08-07T00:10:01.963Z
closed_at: 2026-08-07T00:10:01.963Z
close_reason: "Implemented on feat/quick-file-palette (PR #22): chrome typography rule documented in styles.css with an enforced exception list, .kbd component added and applied, T bound alongside /, palette rows restyled to the file-header weight hierarchy. make verify green."
---
T opens the Quick File palette exactly as / does, matching github.com's go-to-file binding.

In src/metabrowser/static/search_palette.js, handleGlobalKeydown currently early-returns unless event.key === '/'. Accept T as an equal alias.

Requirements:
- same suppression rules as /: no palette when focus is in an editable control, or with alt/ctrl/meta/shift held, during IME composition, or when the event is already defaultPrevented
- case handling: bare 't' opens it; shift+T is excluded by the existing shift guard, so confirm that is the intended behavior
- both bindings surface in the palette hint row via the KBD component
- extend the palette behavior tests to cover T alongside / , including the editable-control suppression case
