---
type: is
id: is-01m78v6n9dwvwgm2pd6dveq6s7
title: "Branch chips: blue by default, and a blue-green instead of purple for the other kind"
kind: task
status: in_progress
priority: 2
version: 2
labels: []
dependencies: []
created_at: 2026-11-12T21:39:13.324Z
updated_at: 2026-11-12T22:21:43.858Z
---
The user, 2026-11-12: branches mostly show in the purple ref color (--git-ref-remote, oklch 0.5 0.1 301.25, which PR branch chips use), too close to a merged PR's purple. Swap so the default branch color is the current blue (--git-ref-local, oklch 0.5 0.1 259.52), and make the other branch color a clearly different aqua or blue-green with lightness and chroma like the blue's, instead of purple. Keep the text-on-chip contrast at WCAG AA in both themes, and check every use of the two tokens (including --git-status-renamed and the commit graph's HEAD lane).

## Notes

2026-11-12: implemented in jlevy/metabrowser#385 (claude/ui-branch-colors-badges to main): ce761662 (branch colors) and 0d66b6f4 (badge centering). Before and after screenshots checked by the coordinator; review A running.
