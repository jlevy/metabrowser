---
type: is
id: is-01m87sppdx4nvpvyjje3jat1cd
title: Check that the app's save-panel downloads are quarantined
kind: bug
status: open
priority: 3
version: 1
spec_path: docs/project/architecture/arch-threat-model.md
labels:
  - security
dependencies: []
created_at: 2026-11-24T22:09:29.017Z
updated_at: 2026-11-24T22:09:29.017Z
---
Threat model T10. Only OpenFileDownloads.seal marks a copy with quarantine; DownloadCoordinator's save-panel downloads are not explicitly marked. Verify whether WKDownload quarantines them, and mark them if not; add a WebKit test.
