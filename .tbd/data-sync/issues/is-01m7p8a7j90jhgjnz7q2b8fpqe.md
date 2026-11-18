---
type: is
id: is-01m7p8a7j90jhgjnz7q2b8fpqe
title: "MANIFEST_READING pin: cover gitlinks, non-UTF-8 paths, tab paths, truncation"
kind: task
status: open
priority: 3
version: 1
labels: []
dependencies: []
parent_id: is-01m7n6v8n050erzeb13c5tasar
created_at: 2026-11-18T02:38:29.448Z
updated_at: 2026-11-18T02:38:29.448Z
---
Review of #530 (B4). test_a_kept_manifest_names_how_it_was_read pins only the branches of _manifest_of the shared diff fixture reaches. Add gitlink (160000) and odd-path entries via update-index --cacheinfo, and a truncated case under a small MAX_MANIFEST_FILES, so a reading change on those branches fails the pin.
