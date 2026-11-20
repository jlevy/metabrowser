---
type: is
id: is-01m7w7pt8rqjk0fk7jne3eh8db
title: WebKit suites ran in parallel on one main thread; a web view's setup blocked it for seconds and starved the click test's 10 s wait
kind: bug
status: open
priority: 3
version: 3
labels: []
dependencies: []
created_at: 2026-11-20T10:23:19.832Z
updated_at: 2026-11-20T17:12:31.507Z
---
PR 640 run 44715405233 job 136217426026 (macOS 26, Xcode 26.6): GitHubViewWebKitTests.swift:213 eventually(within: 10 s) watcher.windows == 1 failed, and windowModifiers was empty. The same app code passed on PR 639 and PR 654 in the same stack. Unrelated to the change under test; rerun once.
