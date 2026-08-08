---
type: is
id: is-01kzfe39s7gn81fs0bffmcnwyt
title: "Quick File catalog only sees ~1% of files: SSE scope is root-depth-2"
kind: bug
status: open
priority: 0
version: 1
labels: []
dependencies: []
created_at: 2026-08-08T00:59:18.182Z
updated_at: 2026-08-08T00:59:18.182Z
---
Files that exist are missing from Quick File results.

Measured on this repo (12,565 files in the inventory):
- the client subscribes at app.js: new EventSource('/api/events?scope=root-depth-2'), so the on-connect snapshot carries depth 0-2 only: 189 entries, 127 files
- /api/tree first paint delivers the same 127 file leaves
- so the catalog holds ~127 of 12,565 files at rest, about 1 percent

Everything deeper only enters the catalog if the user expands that folder, loads Recent, or navigates to the file directly. That is exactly the reported symptom: search a real file, get nothing.

The server already supports scope=all-known and returns the full set (12,565 files, complete: true), so the data is available; the client just never asks for it.

Do NOT simply switch the EventSource to all-known:
- the frame is 5.0 MB for 12.5k files (371 bytes per entry, full FsEntry with size/mtime/labels/active). At the 500,000-file cap that is ~185 MB.
- root-depth-2 is the correct scope for FileStore and tree decoration; widening it changes those semantics and memory too.

The catalog needs path + logical_ext and nothing else: 83 bytes per file measured, ~41 MB at 500k before gzip, and paths compress well.
