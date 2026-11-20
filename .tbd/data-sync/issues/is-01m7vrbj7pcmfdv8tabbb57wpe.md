---
type: is
id: is-01m7vrbj7pcmfdv8tabbb57wpe
title: "Untrusted Markdown: a linked remote image renders as a broken link (wrong target, empty anchor, stray GitHub icons)"
kind: bug
status: open
priority: 1
version: 1
labels: []
dependencies: []
created_at: 2026-11-20T05:55:02.515Z
updated_at: 2026-11-20T05:55:02.515Z
---
Seen on jlevy/markform's README in a cloud mirror: [![alt](https://img.shields.io/...)](https://x.com/...) renders as an empty <a href=destination></a> followed by <a href=image-url>alt</a>, so the visible link goes to the badge image, not its destination; image links to github.com also gain GitHub external-link icons (twice for the CI badge), and a trusted local render adds a GitHub icon after an image-only link that wraps under the badges. GitHub shows badges inline via its camo proxy. Remote images stay blocked in untrusted renders (security policy, qa 5.8); fix the fallback: alt text inside the original link, compact badge-like chip, no external-link icon on image-only links. Owner question pending: load remote images (local proxy or click-to-load) to match GitHub.
