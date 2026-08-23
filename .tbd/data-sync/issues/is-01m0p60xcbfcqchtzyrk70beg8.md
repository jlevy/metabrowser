---
type: is
id: is-01m0p60xcbfcqchtzyrk70beg8
title: Tooltips read at body size, from a token of their own
kind: task
status: closed
priority: 2
version: 2
labels: []
dependencies: []
parent_id: is-01m0ndp6h7a3hx27zbswtknk89
created_at: 2026-08-23T02:08:34.186Z
updated_at: 2026-08-23T02:29:07.968Z
closed_at: 2026-08-23T02:29:07.967Z
close_reason: Fixed on claude/rollup-icon-fixes; verified in a browser.
---
The app's tooltip renders at `--ui-small-font-size` (12px). Requested: it should read at the regular text size, `--body-font-size` (14px), across every tooltip -- and the size should be a named variable rather than a reference to the small-text token, documented in the design system and enforced.

WHY A VARIABLE AND NOT JUST A SWAP. `.custom-tooltip` currently points at `--ui-small-font-size`, which is the token for small CHROME text -- chips, counts, row metadata. Borrowing it makes the tooltip's size a side effect of a decision about chrome, so the next adjustment to small chrome text silently moves every tooltip. A tooltip is prose the reader stops to read; it deserves a token that says so.

SCOPE, as measured:
- `.custom-tooltip` sets the base size. This is the one that changes.
- `.tip-name` sets no size and inherits it.
- `.tip-detail` sets `--ui-small-font-size` explicitly and is a deliberately subordinate line. Settle whether it rides up with the base or stays one step down; staying gives the tooltip a hierarchy it does not have today, where name and detail are the same size.

OUT OF SCOPE: `.kpress-tooltip`. That is KPress's own tooltip inside an embedded document, and this repo deliberately does not flatten KPress's type ramp -- the existing comment beside the radius bridge says so in as many words, and that reasoning has not changed.

ENFORCEMENT. devtools/check_tooltips.py already owns the tooltip rules and runs in `make lint`, so the size rule belongs there: fail if a tooltip rule sets a font-size that is not the tooltip token. That keeps the rule and its check in the same file as the one-tooltip rule rather than in a second place.
