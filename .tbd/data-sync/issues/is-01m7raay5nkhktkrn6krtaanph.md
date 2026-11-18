---
type: is
id: is-01m7raay5nkhktkrn6krtaanph
title: The Metabrowser menu's GitHub link ends in → where every other GitHub link carries the GitHub mark
kind: task
status: open
priority: 4
version: 1
labels: []
dependencies: []
parent_id: is-01m7r8jfm690nwt4rbad8ny3k2
created_at: 2026-11-18T21:52:18.612Z
updated_at: 2026-11-18T21:52:18.612Z
---
Found by the icon catalog (mb-k1k7, docs/design-system-icons.md, Known Departures). The settings menu's title, 'Metabrowser', links to the project on GitHub and shows a → (.menu-title-arrow, server.py's page template) on hover. design-system.md 'External GitHub Links' says general GitHub links use the GitHub mark (destinationGlyphs.github in static/plugin-sdk-views.js, an on-demand bundle; the menu is in the eager shell). A design decision: keep the arrow and state it as the menu title's own affordance, or draw the GitHub mark, which costs startup bytes or a lazy load of the view bundle when the menu opens.
