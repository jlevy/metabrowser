---
type: is
id: is-01m7gd5j7v0sajk1s8xpzkpxcf
title: "GitHub labels: chips colored exactly as GitHub colors them, our sizes kept"
kind: feature
status: closed
priority: 2
version: 4
spec_path: docs/project/specs/done/plan-2026-11-15-files-grouping-diff-summary-and-pull-stacks.md
delegate: claude-code@spud10
labels: []
dependencies: []
parent_id: is-01m7dm3az28qmj39y5hmdq2k0v
hold: null
hold_until: null
created_at: 2026-11-15T20:07:52.826Z
updated_at: 2026-11-17T05:59:11.445Z
started_at: 2026-11-15T20:08:55.171Z
closed_at: 2026-11-16T20:03:31.327Z
close_reason: "Merged into main at 1dcbe93 (stack #446 #464-#478) after the gate and the whole-stack review."
resolution: null
duplicate_of: null
---
The user's request (2026-11-15), verbatim:

"One more change to look up is: let's review how GitHub colors the different labels. And let's see if we can exactly duplicate those colors in our own UI. The tags are colored with a colored background similar to what GitHub colors are. Are these available via the API in any way? If so, why don't we just manage to use the same font sizes but make the chips themselves be colored the way they are in GitHub?"

Findings (coordinator, 2026-11-15):
- GitHub labels carry `color` (6-digit hex, no #) and `description` in both REST and GraphQL.
- The GitHub plugin asks only for `labels { nodes { name } }`: pull_list_refresh.py:94, pulls.py:149, and the page's query. pull_record.py and pull_list.py store label names only.
- Chips render neutral: `.github-pull-label` in builtin_plugins/github/styles.css uses `--border` and `--muted`.
- GitHub's Primer label CSS uses per-label --label-r/g/b and --label-h/s/l custom properties.
  - Light theme: the full color as background; text black or white by perceived lightness (0.2126R + 0.7152G + 0.0722B over 255) against a 0.453 threshold; a border 25% darker in lightness that appears only for very light colors (above 0.96).
  - Dark theme: the color at 0.18 alpha as background; text the label's hue lightened by (0.6 - lightness) when it is darker than 0.6; a border at 0.3 alpha.

Done when:
- Label chips everywhere they appear (PR page header, Pulls rows if they show labels, anywhere else) are colored as GitHub colors them, in light and dark themes, by GitHub's formula. Our chip font size, padding, radius and height stay as they are.
- The color and description are fetched by every query that fetches labels, validated (6 hex digits, else neutral), and persisted in the pull records and list snapshots. The persisted-format change follows AGENTS.md's compatibility rules: no speculative compatibility layer. Name what happens to records cached before the change, for example the existing record version or stamp forcing a refetch, or neutral chips until refresh.
- Each `metab` route that returns labels shows the color in its golden, per AGENTS.md's CLI parity.
- A label's description becomes its chip's tooltip, since it adds information (design system, "Tooltips Add Information"). A label with no description gets no tooltip.
- Chrome checks pin the computed background, text and border colors for a light label, a dark label, a very pale label, and a missing color, in both themes, matched against GitHub's formula.
- docs/design-system.md states the label color rule, and the CHANGELOG says so.
