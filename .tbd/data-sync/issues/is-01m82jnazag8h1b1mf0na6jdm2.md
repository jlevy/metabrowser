---
type: is
id: is-01m82jnazag8h1b1mf0na6jdm2
title: Center the reading column when the navigation pane is hidden
kind: feature
status: in_progress
priority: 0
version: 2
delegate: claude-code@spud10.local
labels: []
dependencies: []
parent_id: is-01m82hy6zdk5e5zzmsan8xhw6q
hold: null
hold_until: null
created_at: 2026-11-22T21:30:12.274Z
updated_at: 2026-11-22T22:06:46.579Z
started_at: 2026-11-22T22:06:46.576Z
---
OS-599 part 1. With the navigation pane hidden (`\` or the chevron), center the capped reading column in the frame instead of pinning it to the left gutter. Flush-right chrome stays where it is, and full-width views are unchanged.

Measured on main 472108123 in headless Chrome. The window is the frame width when the pane is hidden; widths are CSS px.
- README.md and docs/browsing-files.md: the prose column is 988 wide (`--doc-measure` at `DOC_MAX_CHARS_DEFAULT`), at x=56..1044 for every window from 1280 up. The empty band on the right is 236 at 1280, 684 at 1728, 876 at 1920, and 1516 at 2560.
- Folder home (`/`): content at 24..1044 at every width; same empty band.
- Source (activity.py): full width, 24..w-35. Leave it.
- Table (people.csv): a 752-wide grid at 24..776 with the pane hidden. A table grid is not a reading column; leave it left-aligned.

The left edge is deliberate today, not a default. `builtin_plugins/markdown/markdown.css:26-34` forces `margin-inline-start: 0` on `.kpress-doc` and its layout, overriding KPress's own centering. `folder/overview.css:127-129` and `.page-reading-column` (`styles.css` ~5466) pin left too. Chrome tests hold the "shared reading edge" (tests/dom/folder-overview-alignment-chrome.mjs, overview-readme-toc-chrome.mjs, markdown-github-layout-chrome.mjs).

Plan:
1. One shell-owned offset token, set only under `.container[data-nav-collapsed]` and computed in `.preview-pane`'s `kpress-doc` container: `max(0px, (100cqi - <column width>) / 2)`. Do this through a token, not auto margins on a wrapper, because `github/styles.css:74,1674`, `markdown.css:86`, and `styles.css:7879` do arithmetic that assumes `--content-padding-x` is the only side inset.
2. Apply it to the capped reading surfaces: the KPress doc (replacing the `margin-inline-start: 0` pins), the `.md-body` fallback, `.page-reading-column` (PR, commit, placeholder), and the folder Overview cards. Treat the docked TOC grid (`prose | 15rem toc` at >=75rem, `markdown.css:52-57`) as the unit, not the prose alone.
3. View header: move the eyebrow and title with the column so title and prose keep one left edge. `.view-header-end`, the corner controls, stays flush right. **Design decision to confirm with the owner before building.**
4. Leave code, table grids, diff hunks, event and agent logs, the tab bar, and the treemap full width or left as they are. Decide the treemap's 1240px block (`folder/styles.css --tm-max-width`) with the owner.
5. Account for `scrollbar-gutter: stable` on `.preview-pane`, which makes the content box asymmetric: center within the content box, and measure the result.
6. Motion: `nav-collapse.js` slides the frame with WAAPI. The re-centering must not jump at the end of the slide. Either move the offset with the same `--motion-reveal` timing or apply it before the slide. Reduced motion stays instant.
7. Chevron unchanged: it stays in the frame's gutter (the tests at tests/dom/nav-collapse-chrome.mjs:278-280 and 306 must still pass).

Evidence (AGENTS.md parity): extend parity row `shell.nav-collapse-paint` (arch-parity-registry.md ~390) with a headless-Chrome test that measures the column's center against the frame's at 1280, 1920, and 2560, with the pane shown and hidden, for a Markdown doc, a folder, a PR page, and a source file (unchanged). The survey script that produced the numbers above is the seed. Rewrite design-system.md "Hiding the Navigation Pane" (~5003; it says the page slides left to fill the window) and "Reading Width" (~782). Update the alignment tests and stylesheet-text pins in tests/test_design_vocabulary.py:1357-1373 and 1821-1851.
