---
type: is
id: is-01m26s726nk6q4ga3w1sj8m8me
title: Resolve embedded Markdown fragment hrefs to their source document
kind: bug
status: in_progress
priority: 1
version: 2
labels:
  - release-hardening
  - markdown
dependencies: []
created_at: 2026-09-10T23:07:31.412Z
updated_at: 2026-09-10T23:10:05.179Z
---
Final Astra-max review reproduced fragment-only links in embedded README/transcluded Markdown staying as #fragment, so modified-click, target=_blank, and Copy Link resolve against the folder/current page instead of the embedded source. Preserve fragment-only hrefs only for the primary document needed by KPress TOC, and add exact production-module coverage.
