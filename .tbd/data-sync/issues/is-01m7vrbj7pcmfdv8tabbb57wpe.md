---
type: is
id: is-01m7vrbj7pcmfdv8tabbb57wpe
title: Load remote images in cloud-repo Markdown by default, like GitHub; a privacy setting (off by default) blocks them
kind: bug
status: in_progress
priority: 1
version: 3
delegate: claude-code@spud10.local
labels: []
dependencies: []
hold: null
hold_until: null
created_at: 2026-11-20T05:55:02.515Z
updated_at: 2026-11-20T05:56:00.479Z
started_at: 2026-11-20T05:56:00.070Z
---
Seen on jlevy/markform's README in a cloud mirror: [![alt](https://img.shields.io/...)](https://x.com/...) renders as an empty <a href=destination></a> followed by <a href=image-url>alt</a>, so the visible link goes to the badge image, not its destination; image links to github.com also gain GitHub external-link icons (twice for the CI badge), and a trusted local render adds a GitHub icon after an image-only link that wraps under the badges. GitHub shows badges inline via its camo proxy. Remote images stay blocked in untrusted renders (security policy, qa 5.8); fix the fallback: alt text inside the original link, compact badge-like chip, no external-link icon on image-only links. Owner question pending: load remote images (local proxy or click-to-load) to match GitHub.
