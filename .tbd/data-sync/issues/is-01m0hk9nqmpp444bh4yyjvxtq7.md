---
type: is
id: is-01m0hk9nqmpp444bh4yyjvxtq7
title: Nav filter counts freeze mid-crawl and never refresh
kind: bug
status: closed
priority: 2
version: 3
labels: []
dependencies: []
parent_id: is-01m0gfpa3nt74hvrnqbyqhn0ya
created_at: 2026-08-21T07:24:20.594Z
updated_at: 2026-08-21T18:31:17.467Z
closed_at: 2026-08-21T15:46:52.934Z
close_reason: null
---
Leave a page open across a large crawl and the nav filter counts freeze at whatever the
crawl had reached, while everything around them finishes correctly.

Reproduced on a 400,000-file tree: open /view/ as the scan starts, wait for it to reach
done, then open the Modified within menu without reloading.

  menu says       Past day / week / month  198,998
  server says     ['24h', 400002, 0], ['7d', 400002, 0], ['30d', 400002, 0]
  page header     400,002 files, correct
  panel totals    400,002 files, correct

So the page has the right total in two places and a stale one in the filter menu. A
reload fixes it, which is the tell: the data is fine, the menu is holding an older
response.

The same shape appears for the type and size menus, which come from the same /api/tree
payload (summary, extensions, canonical_extensions, type_families, type_presets,
recency_tallies).

Pre-existing, and specifically not from the tally memo added in this branch: reproduced
at 40df198, before that work, with the same tree and the same steps, showing 198,998
against a server reporting 400,002. Confirmed again after the memo, so it is unchanged
either way. The server response was verified correct at the moment the stale menu was
open, so this is entirely on the client side.

Worth locating in app.js: scheduleRootSummaryRefresh fetches /api/tree?depth=0 and
patches the summary row, and the header total does update. Either the filter menus read
from a separate cached copy that the refresh does not touch, or they render once and are
never re-rendered. The final refresh after status flips to done is the one that has to
land.

Counts that a reader will act on -- picking "past day" to narrow a large tree -- should
not be silently short by half.
