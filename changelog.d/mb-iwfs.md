- **A diff’s File type menu filters again in the macOS app and Safari.** Choosing
  Documentation, or any group, family, or extension, in the File type menu of a pull
  request’s or a stack’s Changes did nothing there: the menu closed and the diff kept
  every file. WebKit gives focus to the preview pane on a press on a button, and since
  menus began closing alike, that focus arriving outside the menu closed it under the
  press, before its click.
  Focus that a press in a menu moves is now that press’s own
  ([Every Menu Closes Alike](docs/design-system.md#every-menu-closes-alike)).

- **The File type menu stays open after a choice** in every browser, so several types
  can be chosen in turn.
  A diff with Markdown files closed it as each choice mounted.
