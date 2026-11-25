---
type: is
id: is-01m885apq00nbzjegndxn261r9
title: "Mac app reader messages: audit alerts and status views, and check the Swift copy"
kind: task
status: open
priority: 2
version: 1
labels: []
dependencies: []
parent_id: is-01m87ky2a36j5yg4pf9827xxd6
created_at: 2026-11-25T01:32:39.002Z
updated_at: 2026-11-25T01:32:39.002Z
---
From review A6 on PR #801 (https://github.com/jlevy/metabrowser/pull/801#pullrequestreview-6049962996). The guide (docs/design-system-messages.md) now says it covers the macOS app's alerts and status views, but tests/test_reader_messages.py reads no Swift. Sites the review named: apps/macos/Sources/Metabrowser/FolderPage.swift:527 and :755 (The page did not load: error.localizedDescription); apps/macos/Sources/ShellCore/Web/OpenFilePlan.swift:21-24; OpenFileDownloads.swift:66, :110, :121; DownloadCoordinator.swift:74, :93, :107; apps/macos/Sources/Metabrowser/StatusView.swift:121-122 (Recent server output shown inline, not under a disclosure). Rewrite each to one statement and one remedy with the detail in the log, decide StatusView's layout, and add a Swift string-literal scan if cheap. Verify with the macos-app workflow.
