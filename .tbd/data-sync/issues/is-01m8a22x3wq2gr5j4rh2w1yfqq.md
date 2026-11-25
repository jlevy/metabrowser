---
type: is
id: is-01m8a22x3wq2gr5j4rh2w1yfqq
title: "Authors follow pull requests: Quick Search, ref selector, guide file bars, merged header"
kind: task
status: open
priority: 2
version: 1
labels: []
dependencies: []
created_at: 2026-11-25T19:14:26.550Z
updated_at: 2026-11-25T19:14:26.550Z
---
The design-system rule "Authors Follow Pull Requests" (docs/design-system.md, added in PR #843) says: wherever a row names a pull request by its number or stack place, its author follows, after a muted dot, in the shell's actor identity (bold name, 16 px avatar, `--github-pull-row-avatar-size`), unless the surface has no room for it, and the rule names each exemption with a measured reason. PR #843 did the Pulls row, the stack menu members (authors from the stacks route), and the guide's pull request rows. These surfaces still show a number with no author, each needing a route or a measurement, so they were left out of #843:

1. Quick Search pull request results (src/metabrowser/static/search-palette.js `appendPullResult`, results from search-controller.js): the description line is "#N · State". The pull search's results carry no author; add author and avatar to the result and draw the identity after the number, or measure and exempt.
2. The ref selector's branch row pull line (src/metabrowser/static/source-ref-selector.js `pullLine`, data from `RefPull` in src/metabrowser/source_routes.py): "icon #N title +k". `RefPull` has no author. The selector is a narrow dropdown, so measure the room first.
3. A guide's file of another pull request (src/metabrowser/builtin_plugins/github/guided-review.js `referenceBar`, `.github-pull-guide-reference-pull`): "#N path" in a diff file bar whose one line belongs to the path. Measure the room against a long path before adding or exempting.
4. A merged pull request's page header: its sentence names the merger ("octo merged 6 commits", as github.com does), so the header's "#N" has no author once merged. Decide whether the header should name the author too.

The stack page's member rows are being rebuilt separately and take the rule there. Each surface that adds the author updates the rule's table in docs/design-system.md; each that cannot fit it is added to the rule's exemptions with its measurement.
