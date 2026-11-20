---
type: is
id: is-01m7w7pt8rqjk0fk7jne3eh8db
title: GitHubViewWebKitTests click test sees no window and no command modifier (cause under investigation)
kind: bug
status: open
priority: 3
version: 2
labels: []
dependencies: []
created_at: 2026-11-20T10:23:19.832Z
updated_at: 2026-11-20T16:40:20.280Z
---
PR 640 run 44715405233 job 136217426026 (macOS 26, Xcode 26.6): GitHubViewWebKitTests.swift:213 eventually(within: 10 s) watcher.windows == 1 failed, and windowModifiers was empty. The same app code passed on PR 639 and PR 654 in the same stack. Unrelated to the change under test; rerun once.
