---
type: is
id: is-01m82hy6zdk5e5zzmsan8xhw6q
title: More gracefully responsive layout and padding for wider widths
kind: task
status: in_progress
priority: 0
version: 2
labels: []
dependencies: []
created_at: 2026-11-22T21:17:34.575Z
updated_at: 2026-11-22T21:17:35.293Z
extensions:
  linear:
    id: 79e3aeab-0661-464d-a802-5624c419ac9a
    linked_at: 2026-11-22T21:17:35.293Z
---
Right now if you hide the nav column, the text slides all the way to the left, which doesn't really make sense for a clean view. In that case the main text should be centered and it should be a little more graceful and easy to read while keeping most of the layouts the same. Certain things that are already flush right, like some of the icons and so on, would stay there, but the main content would be in a more distraction-free mode.

Another related thing is that, for wider widths, we could add more padding to certain columns around the nav panel. It could be wider and the padding and/or margins around the components of the main window could be a little larger too, to make it less cramped. For narrower widths it's good that we have the tight appearance because it's more efficient.
