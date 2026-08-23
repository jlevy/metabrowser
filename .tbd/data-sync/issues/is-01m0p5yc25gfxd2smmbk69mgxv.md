---
type: is
id: is-01m0p5yc25gfxd2smmbk69mgxv
title: Rollup child rows should carry the generic file icon, not a per-entry one
kind: bug
status: closed
priority: 2
version: 2
labels: []
dependencies: []
parent_id: is-01m0ndp6h7a3hx27zbswtknk89
created_at: 2026-08-23T02:07:10.902Z
updated_at: 2026-08-23T02:29:07.081Z
closed_at: 2026-08-23T02:29:07.080Z
close_reason: Fixed on claude/rollup-icon-fixes; verified in a browser.
---
Child rows inside the special rollups -- "Other types" and the no-extension group -- still resolve an icon per entry, through the sixteen-entry extension table in static/app.js rather than through the registry. Requested: they should all carry the GENERIC file icon, the grey page.

WHY IT IS THE RIGHT ICON. mb-sa13 established that an icon names a FAMILY: the family row carries one and the extensions inside it carry none, because the family above already says what they are. These rows have no family by definition -- that is what puts them under "Other types" in the first place -- so there is no family icon to show. A neutral page is the honest mark, and it keeps the rows aligned with the family rows above them.

WHY IT IS ALSO THE RIGHT MECHANISM. Resolving per entry reaches back into the second taxonomy that mb-xrh8 is about. Whether a given entry gets a specific glyph then depends on whether that extension happens to be one of the sixteen the old table knows, which is not a distinction the registry makes and not one a reader can predict.

MEASURED IN THIS REPO, which is why the fix is about determinism rather than about what is on screen here: all 18 child rows currently render the generic page already, because none of these particular extensions is in the old table. But `fileTypeIcon("x.js")` does return a distinct glyph, so a directory whose unfamilied entries happen to be in the table renders type-specific icons in this list. That is what makes it unpredictable rather than merely wrong.

SCOPE. Both kinds of child under a special parent: extension rows under "Other types", and whole-filename rows under the no-extension group. They are the same class of thing -- an unfamilied entry in a rollup. Note this does mean Dockerfile and Makefile lose any recognisable glyph they might get elsewhere; if those should keep an identity, that is a separate decision and belongs with mb-xrh8, since it needs the registry to name it.

Aggregate "N more" rows already carry no icon and keep none: they stand for a set, not a file.
