---
type: is
id: is-01m6ywt33pjcd0x0x4cv7zyc85
title: Coordinate duplicate missing GitHub CLI notices across Pulls and PR detail
kind: bug
status: open
priority: 2
version: 1
labels: []
dependencies: []
created_at: 2026-11-09T00:54:54.321Z
updated_at: 2026-11-09T00:54:54.321Z
---
With a process-local PATH that contained Git but no GitHub CLI, the built-in browser opened public pallets/markupsafe PR #507 from its warm cache on source equivalent to a53907948f348345ea0c6cbafbfe138c6513ba70. Cached Conversation, actual Changes patches and Checks were usable. The setup guidance linked to cli.github.com and showed `gh auth login --hostname github.com`. With both the Pulls sidebar and PR detail visible, each pane displayed its own visible Install GitHub CLI link for the same `gh_missing` cause. The clipped live region is separate from the two visible notices.

Coordinate the same-cause notices so readers see one visible setup action when both surfaces show that cause. When the sidebar is hidden or absent, keep an accessible, actionable detail notice. Preserve the install and sign-in guidance, status announcements, distinct failures, retry behavior and cached access. Verify both visibility states with a focused session. The observation used a scoped missing-tool environment and source execution. Related closed mb-asz3 delivered actionable guidance across views; this is a separate coordination follow-up.

Evidence: release-followups-r3-20261108/no-gh-source-browser.json.
