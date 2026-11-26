- **A press in a menu that brings no click no longer keeps the menu open** against focus
  that arrives outside it afterwards, as from an assistive technology or a native menu
  command. Such a press, on a disabled row say, is over a moment after the button comes
  up, and at once when the browser takes it for a scroll or a context menu
  ([Every Menu Closes Alike](docs/design-system.md#every-menu-closes-alike)).

- **Plugin SDK:** `filterControls.bind` answers for every dropdown inside the element it
  is given, so bind each control’s own element and not a region that holds another bound
  control. `menus.dismissible`’s `opened()` again closes any other open menu, whichever
  handle holds it ([Menus](docs/plugins.md#menus)).
