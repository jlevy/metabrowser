---
type: is
id: is-01m7zt8s6hyeah3vfpm02rb6zf
title: Move repository heading details into a root disclosure menu
kind: feature
status: in_progress
priority: 2
version: 3
refs:
  - kind: pr
    url: https://github.com/jlevy/metabrowser/pull/685
    at: 2026-11-21T19:56:48.079Z
delegate: codex@spud10
labels: []
dependencies: []
parent_id: is-01m7wyrvxk2xx44pqtqmy5cq5g
hold: null
hold_until: null
created_at: 2026-11-21T19:45:26.224Z
updated_at: 2026-11-21T19:56:48.081Z
started_at: 2026-11-21T19:45:29.779Z
---
Make the root heading disclose its source or checkout type and the existing hover statistics, preserving the navigation affordance and keyboard access. At the root only, provide Open Repository and Copy Repository URL when the server can supply a supported canonical repository URL. Ordinary folders, nested views, and unknown remotes must not gain repository URL actions. Exercise the supported checkout and mirror cases, plus the local folder and no-supported-remote cases.
