---
type: is
id: is-01m7gf9b7eveb6p7pv6m4erz04
title: "Stack keys: Control-N/P do nothing on a PR page reached by Back or Forward"
kind: bug
status: open
priority: 2
version: 3
spec_path: docs/project/specs/done/plan-2026-11-15-files-grouping-diff-summary-and-pull-stacks.md
labels: []
dependencies: []
parent_id: is-01m7wys8y3epj61gncgjakhsd0
created_at: 2026-11-15T20:44:53.869Z
updated_at: 2026-11-20T17:09:54.168Z
---
Found by the mb-6y0g (reveal on navigate) agent, 2026-11-15, and reproduced on ba65d9be7 (#457's tip) with its changes swapped out, so it predates mb-6y0g.

On a freshly started server, after reaching a pull request page in a stack by Back or Forward, Control-N and Control-P (Next and Previous in stack, mb-lnqj) do nothing: the keys reach the page, but no handler takes them. Reaching the same page by loading `/pull/7` directly works. The mb-6y0g Chrome check walks the stack from a loaded page to avoid it.

Done when the stack keys work on a pull request page however it was reached (load, link, Quick Search, Back, Forward), the cause is named (likely `pulls-nav`'s `hasStack()` availability or the stack index not being re-read on a history entry), and a Chrome check or browserless session covers the Back and Forward cases.
