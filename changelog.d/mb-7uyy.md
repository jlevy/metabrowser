- **Every menu closes alike.** Group by, Modified within, File type, the branch chooser,
  the gear, the root details, a branch or tag name’s menu, View on GitHub, the pull
  request stack menu, and a table’s column menus now each close on a press or a tap
  outside them, on a second press of their button, on Escape, which gives focus back to
  the button, on a press in a preview’s frame, and when focus moves elsewhere, and
  opening one closes any other.
  The Files dropdowns used to stay open on a press on the filter bar beside them, on the
  drawer’s chevron, or on Show ignored, and no menu closed on a press in a preview.
  The press that closes a menu still acts on what it lands on
  ([Every Menu Closes Alike](docs/design-system.md#every-menu-closes-alike)).

- **Plugin SDK:** `metabrowser.menus.dismissible(menu)` gives a plugin’s own menu the
  same closing; feature-detect it with `mb.menus?.dismissible`
  ([Menus](docs/plugins.md#menus)). `PLUGIN_SDK_VERSION` is unchanged.
