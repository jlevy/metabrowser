---
type: is
id: is-01m7vabmvnertkaeg2cs401pq6
title: "KPress: keep the rest of GitHub's layout attributes and table alignment (follow-ups from mb-5xq7)"
kind: task
status: open
priority: 3
version: 1
labels: []
dependencies: []
created_at: 2026-11-20T01:50:25.139Z
updated_at: 2026-11-20T01:50:25.139Z
---
Found while fixing mb-5xq7 (#626). In KPress, not Metabrowser: sanitized mode drops valign, hspace, vspace, clear, nowrap, dir, li[value], details[open], which github.com keeps; GFM pipe-table column alignment is lost because KPress strips style; KPress tables are min-width:100% so table align/width have no effect; a 1rem block margin on images raises inline badges; KPress centers a standalone Markdown image as a figure, which github.com does not. Evidence: review-527-c attic/readme-align/ (github-layout.png vs ours-layout-after*.png).
