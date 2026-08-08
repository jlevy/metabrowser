---
type: is
id: is-01kzfe3r2xjtcrtm239extt3gv
title: Catalog resync wipes coverage and removals are O(n) per op
kind: bug
status: open
priority: 2
version: 1
labels: []
dependencies: []
created_at: 2026-08-08T00:59:32.828Z
updated_at: 2026-08-08T00:59:32.828Z
---
Two robustness defects that get worse as coverage grows toward the 500,000-file cap.

1. fs.resync_required calls knownFileCatalog?.clear() in app.js, dropping every observed path. If it fires while the palette is open the next keystroke searches an empty catalog until a fresh snapshot lands. It should re-seed from the incoming snapshot rather than leave a hole, and the palette should report indexing rather than 'no matches'.

2. known_file_catalog.removeWithoutRevision() scans every key in the map for each removed path, to catch directory-prefix removals. That is O(n) per op; a burst of change ops against a 500k-entry catalog is O(n*m) on the UI thread, which will jank an open search. Needs a prefix-aware structure or a deferred sweep.
