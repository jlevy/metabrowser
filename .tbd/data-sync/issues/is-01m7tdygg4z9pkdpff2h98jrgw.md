---
type: is
id: is-01m7tdygg4z9pkdpff2h98jrgw
title: "Mirror heading: drop the ref and commit beside the repository name; commit IDs take the size of the text around them"
kind: bug
status: in_progress
priority: 2
version: 2
delegate: claude-code@spud10
labels: []
dependencies: []
hold: null
hold_until: null
created_at: 2026-11-19T17:33:54.562Z
updated_at: 2026-11-19T17:34:26.175Z
started_at: 2026-11-19T17:34:26.174Z
---
Owner, 2026-11-19, verbatim: "when I open a bare cloud repo the top level title of the repo now has a branch name and a hash right next to the title. These should not be there. They are clutter. Also, they're the wrong font size on the hash name, so there's some sort of design system inconsistency anyway we sholud make sure our design system always renders monospace hashes as the size of the fonts surrounding them. But in any case, these should not be showing anyway. The branch chooser below indicates the branch." Source: server.py _pin_label_html adds .header-revision .header-ref and .header-revision.git-commit-sha; styles.css .git-commit-sha has a fixed font-size var(--nav-font-size), with per-context overrides (.source-ref-selector, .source-freshness).
