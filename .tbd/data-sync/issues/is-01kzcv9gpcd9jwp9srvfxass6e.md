---
type: is
id: is-01kzcv9gpcd9jwp9srvfxass6e
title: Quick File list flickers on every keystroke
kind: bug
status: open
priority: 1
version: 1
labels: []
dependencies: []
created_at: 2026-08-07T00:52:10.059Z
updated_at: 2026-08-07T00:52:10.059Z
---
Typing in the palette blanks the result list for a frame before the new results paint.

Cause: search_controller.js runProviders() calls publishComposition('searching') before any provider has returned, so the published state carries results: []. The palette's consumeState renders that empty composition, emptying the listbox, and refills it when the provider resolves a few ms later. Per keystroke the list goes previous results -> empty -> new results.

A second, smaller flash comes from the status line: runSearch paints 'Searching N observed files…' synchronously, then replaces it with the result message about 30 ms later.

Fix in the palette, not the controller: progressive publishing is deliberate and matters once a server provider joins the local one. The presentation layer should hold the previous rows until real results (or a completed empty search) replace them, the same way selectFile keeps the previous file on screen during a fast fetch rather than flashing a spinner. Give the 'Searching…' status the same delayed treatment as LOADING_INDICATOR_DELAY_MS in app.js.
