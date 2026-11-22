---
type: is
id: is-01m82jnfmjhcr55c383063twaa
title: Step the main page's gutters up at wide pane widths
kind: feature
status: open
priority: 1
version: 1
labels: []
dependencies: []
parent_id: is-01m82hy6zdk5e5zzmsan8xhw6q
created_at: 2026-11-22T21:30:17.100Z
updated_at: 2026-11-22T21:30:17.100Z
---
OS-599 part 2a. Grow the main page's gutters and the spacing around its components in steps as the pane gets wider. Narrow panes keep today's tight 24px.

Measured on main 472108123: `--content-padding-x` is 24px and `--content-padding-y` is 16px at every width from 1024 to 2560 (styles.css:730-731), on a frame up to 2560 wide.

Constraints found:
- Responsive rules in this shell are container queries on `.preview-pane` (`container: kpress-doc / inline-size`, styles.css:3444), because viewport queries misstate the pane's width (comment at styles.css:3439-3441). There are no viewport `@media` queries and no breakpoint tokens yet. Keep it that way here: step the tokens inside `@container kpress-doc (min-width: …)` rules on `.preview-pane`.
- Use discrete steps, not a fluid `clamp()`. The header query at styles.css:4919 `(width < 680px)` is a literal derived from `2 * --content-padding-x + …` (comment 4906-4918), and `var()` is not allowed in container conditions. With steps that start well above 680, the narrow band keeps 24px and the literal stays true. tests/test_view_header_chrome.py:198-225 recomputes it; keep that test passing unchanged.
- The chevron's position (`.nav-collapse-toggle`, styles.css:3305) is computed from `--content-padding-x` on the frame, outside the container. Decide whether it stays centered in a wider gutter. The design system says it "fills the main frame's gutter".
- Plugins read the token rather than literals (diff, sqlite, github, markdown, agents, event_log, binary), so they follow. Check `github/styles.css:74,1674`, `markdown.css:86`, and `styles.css:7879`, which subtract `2 * --content-padding-x`.
- Vertical rhythm: consider `--content-padding-y` and the spacing between view-header rows at the same steps.

Measure before bounding (AGENTS.md): pick the step widths and values from screenshots at 1280, 1728, 1920, and 2560 with the pane shown and hidden. Record the measurement beside the constants in styles.css, not in prose. Evidence: a headless-Chrome check of the gutter at each step, a parity row or extension (`shell.view-header-layout` ~370 is the neighbor), and design-system.md "Token Layers" (~29) and "View Headers" (~369).
