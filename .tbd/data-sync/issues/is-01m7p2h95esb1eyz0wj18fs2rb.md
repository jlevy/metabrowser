---
type: is
id: is-01m7p2h95esb1eyz0wj18fs2rb
title: Trusted TOC scroll-spy stops following the reader after in-app navigation onto a page sharing heading ids (#517 review A1)
kind: bug
status: open
priority: 2
version: 3
labels:
  - ui
  - toc
  - files
dependencies: []
created_at: 2026-11-18T00:57:29.005Z
updated_at: 2026-11-18T01:07:11.635Z
---
Review A1 on jlevy/metabrowser#517 (merged as dcf2bcfa8 before the review was published).

After in-app navigation onto a page whose headings share ids with the page before, a trusted render's table of contents stops following the reader: the active entry stays the one marked at arrival (the first entry, if the page before was at its top, or none; measured "Section 1" in headless Chrome 152 on 2026-11-17, scrolled to Section 5), and with collapse depth 1 the deeper entries of the section being read stay folded. Entry clicks still work. Under --untrusted every route works, because inert-toc.js resolves headings inside its own article.

Routes that fail: README.md to its folder's Overview; a folder's Overview to another whose README shares heading names; an Overview to its README.md; README.md to a copy of it. A full page load works, as does any route between pages with different ids.

Cause: the shell lays the incoming page out in a connected, inert stage while the outgoing page stays in the pane (static/app.js, renderFile; docs/project/architecture/arch-browser-shell.md, "Staged Handoff"), and the active view's mount settles before the stage is committed. KPress 0.3.8's toc.js resolves each entry's heading with document.getElementById(id) (wireToc, headingTargets and the IntersectionObserver loop), which returns the outgoing page's heading; the observer then watches nodes removed at commit. The SDK documents that a staged renderer must scope DOM access to its container (docs/plugins.md, "Registration and Lifecycle"), which toc.js does not.

The plugin SDK has no commit signal: mb.viewState.subscribeActive does not fire at commit, because the shell marks the staged tab content active and the commit sets the same element active again, a no-op in view-state.js#setActive.

Fixes:
(a) In KPress (first-party), resolve each entry's heading inside the table of contents' own document (the article or the toc's root) rather than document.getElementById, publish, and raise the kpress pin. This also fixes file to file. Preferred.
(b) In Metabrowser, wire KPress's table of contents after the stage is committed, or dispose and re-run it then. Needs a commit signal the SDK offers plugins; adding one is an SDK change of its own.

tests/dom/overview-readme-toc-chrome.mjs carries the in-app step (README.md, then metabrowser.navigation.open({path: ""}), scroll Section 5 to the top, assert an active entry) as an expected failure under the trusted profile naming this bead. Once fixed, it reports an unexpected pass: remove the expectation.
