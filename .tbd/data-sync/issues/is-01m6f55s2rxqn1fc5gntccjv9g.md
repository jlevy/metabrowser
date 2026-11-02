---
type: is
id: is-01m6f55s2rxqn1fc5gntccjv9g
title: A pull-request URL ending in /files opens on Conversation
kind: bug
status: open
priority: 1
version: 1
labels:
  - release:v0.12.0
dependencies: []
parent_id: is-01m6f3n89kn7ztmfhrzswxnsgz
created_at: 2026-11-02T22:13:14.964Z
updated_at: 2026-11-02T22:13:14.964Z
---
Found 2026-11-02 writing the guide. metab https://github.com/owner/repo/pull/123/files serves /pull/123: builtin_plugins/github/urls.py near line 472 drops the tail and the banner prints the Conversation address. A reader who copies a Files changed URL from GitHub lands on the wrong tab. Make the served address honor /files, as a blob URL keeps its line anchor, and update docs/reviewing-pull-requests.md and the command-line section, which currently document the behavior as it stands.
