---
type: is
id: is-01m0nsv8y2d2m4c9jkwebjct17
title: "Two tooltips on one element: ban native title where the app has its own tooltip"
kind: bug
status: open
priority: 1
version: 1
labels: []
dependencies: []
parent_id: is-01m0ndp6h7a3hx27zbswtknk89
created_at: 2026-08-22T22:35:46.497Z
updated_at: 2026-08-22T22:35:46.497Z
---
The nav panel's heading shows two tooltips at once: the browser's native one, from a `title` attribute, and the app's own tooltip component. Two tooltips for one element, on different timers and in different places, is worse than either alone.

The immediate cause is that both mechanisms are in use on the same surface. `setServedRoot` writes `pathEl.title`, and the crumbs in `headerAddressHtml` gained a `title` in the mb-fos4 fix, at the same time as the app has had its own anchored tooltip since the 0.6.0 tooltip work.

REQUESTED, and the part that matters more than the one fix: the app has its own tooltip, so a native `title` should never be the mechanism on a surface the app controls. Make that a rule rather than a habit -- document it where a reader will meet it, and enforce it with a check, since a `title=` is a single character away from being reintroduced and nothing currently notices.

Points to settle while doing it:
- `title` is still the right answer in places the app's tooltip cannot reach or where it would be wrong: `aria-label` is not a substitute, and a control whose only label is an icon still needs an accessible name. So the rule is about the *visible* tooltip, not about the attribute everywhere.
- Decide the boundary for plugins, which get `mb.tooltip` through the SDK and can also write `title` into their own HTML.
- Whatever the check is, it should say which element and which file, so the fix is obvious.
