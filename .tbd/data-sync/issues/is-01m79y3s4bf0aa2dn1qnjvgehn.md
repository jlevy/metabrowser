---
type: is
id: is-01m79y3s4bf0aa2dn1qnjvgehn
title: Toggles never select text when clicked
kind: bug
status: open
priority: 2
version: 1
labels: []
dependencies: []
created_at: 2026-11-13T07:49:19.113Z
updated_at: 2026-11-13T07:49:19.113Z
---
The user, 2026-11-12: toggles such as a folder's toggle in the nav panel and the rendered diff view's expanders that reveal more blocks can select text when clicked. A proper toggle (anything with a rotating > chevron) must never do this, consistently, as a design-system rule. Stacked on #390's branch; does not change the merge sequence.
