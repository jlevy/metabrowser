---
type: is
id: is-01m7vrbj7pcmfdv8tabbb57wpe
title: Load remote images in cloud-repo Markdown by default, like GitHub; a privacy setting (off by default) blocks them
kind: bug
status: closed
priority: 1
version: 6
delegate: claude-code@spud10.local
labels:
  - linear
dependencies: []
hold: null
hold_until: null
created_at: 2026-11-20T05:55:02.515Z
updated_at: 2026-11-20T17:00:12.221Z
started_at: 2026-11-20T05:56:00.070Z
closed_at: 2026-11-20T08:57:57.241Z
close_reason: "Landed in #644: remote images on by default with a Block remote images setting, sandboxed shell, no-referrer"
resolution: null
duplicate_of: null
---
Seen on jlevy/markform's README in a cloud mirror: [![alt](https://img.shields.io/...)](https://x.com/...) renders as an empty <a href=destination></a> followed by <a href=image-url>alt</a>, so the visible link goes to the badge image, not its destination; image links to github.com also gain GitHub external-link icons (twice for the CI badge), and a trusted local render adds a GitHub icon after an image-only link that wraps under the badges. GitHub shows badges inline via its camo proxy. Remote images stay blocked in untrusted renders (security policy, qa 5.8); fix the fallback: alt text inside the original link, compact badge-like chip, no external-link icon on image-only links. Owner question pending: load remote images (local proxy or click-to-load) to match GitHub.

## Notes

2026-11-20: implemented in PR #644 (branch claude/remote-image-link-fallback). Owner scope change: untrusted Markdown now loads https images (CSP img-src https:, referrerpolicy=no-referrer, no proxy); badges keep their link, the not-loaded fallback is a chip (.mb-image-fallback) inside the original link with the image URL in data-tip-text; no external-link icon on image-only links (decorateExternalLink/holdsImagesOnly). Privacy setting 'Block remote images' (Metabrowser menu, off by default): host-wide cookie metabrowser.blockRemoteImages read by the server on the page request (narrows img-src, sets METABROWSER_SETTINGS.BLOCK_REMOTE_IMAGES); applies to untrusted renders only (trusted folders unchanged by design). Open: PR/commit text now also load remote images (one hardener); residual risk of https://localhost image GETs noted in SECURITY.md; startup-script budget has 15 bytes of slack.
