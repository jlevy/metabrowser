---
type: is
id: is-01m79y3s4bf0aa2dn1qnjvgehn
title: Toggles never select text when clicked
kind: bug
status: closed
priority: 2
version: 3
labels: []
dependencies: []
created_at: 2026-11-13T07:49:19.113Z
updated_at: 2026-11-13T09:02:42.610Z
closed_at: 2026-11-13T09:02:42.609Z
close_reason: "Done in jlevy/metabrowser#394 (cc2392b7, 1962d8d0, fixes through 73dd5cd2): reviews A then B (approve with a Low, fixed). Merges once #390 lands and CI is green."
resolution: null
duplicate_of: null
---
The user, 2026-11-12: toggles such as a folder's toggle in the nav panel and the rendered diff view's expanders that reveal more blocks can select text when clicked. A proper toggle (anything with a rotating > chevron) must never do this, consistently, as a design-system rule. Stacked on #390's branch; does not change the merge sequence.

## Notes

2026-11-13: jlevy/metabrowser#394 (claude/ui-toggles-no-select, stacked on #390), cc2392b7. Cause: WKWebView ignores unprefixed user-select, so the app never honored it; Chrome's rendered-diff summary had no rule. One .disclosure-toggle/summary rule with the -webkit- half, every chevron toggle classed, every user-select paired. Screenshots checked; review A running.
