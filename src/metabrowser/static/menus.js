// How every menu closes (docs/design-system.md, "Every Menu Closes Alike"): a press or a
// tap outside it and its trigger, focus arriving outside them, the window losing focus,
// and Escape close it, and opening one closes any other. Its trigger's own click toggles
// it, so a second press closes it. A press that closes a menu still acts on what it lands
// on, as a press beside the branch chooser always has. Opening one with focus outside it
// moves focus to its trigger.
//
// Every menu in the shell and its built-in plugins closes through this, and a plugin's
// menu does through `metabrowser.menus.dismissible` (docs/plugins.md, "Menus");
// tests/test_menu_dismissal.py fails a menu surface that does not. It arrives with the
// shell's tools, after the first tree, since nothing here is needed to paint one; the
// SDK's `menus.dismissible`, in static/filter-controls.js, asks for it when a menu opens
// sooner.

/** @param {Window} global */
((global) => {
  /** @typedef {{menu: MetabrowserDismissibleMenu, doc: Document}} OpenMenu */

  /** The menus open now, each with its document, in the order they opened.
   * @type {Set<OpenMenu>} */
  const openMenus = new Set();
  /** Each document's listeners, held only while one of its menus is open.
   * @type {Map<Document, () => void>} */
  const listening = new Map();

  /** @param {MetabrowserDismissibleMenu} menu */
  const triggerOf = (menu) => (typeof menu.trigger === "function" ? menu.trigger() : menu.trigger);

  /**
   * The open menus of `doc`, less any that closed or went since they opened: a menu its
   * own code closed without saying so leaves at the next event.
   * @param {Document} doc
   */
  function openMenusOf(doc) {
    const open = [];
    for (const entry of openMenus) {
      if (!entry.menu.isOpen() || triggerOf(entry.menu)?.isConnected === false) {
        openMenus.delete(entry);
      } else if (entry.doc === doc) {
        open.push(entry);
      }
    }
    return open;
  }

  /**
   * Close one open menu for one of the reasons `MetabrowserMenuClose` names. Escape also
   * gives focus back to the trigger, when the menu's own close left it in place.
   * @param {OpenMenu} entry
   * @param {MetabrowserMenuClose} how
   */
  function closeMenu(entry, how) {
    const trigger = triggerOf(entry.menu);
    openMenus.delete(entry);
    entry.menu.close(how);
    if (how === "escape" && trigger?.isConnected && entry.doc.activeElement !== trigger) {
      trigger.focus({ preventScroll: true });
    }
    unlisten(entry.doc);
  }

  /** @param {Document} doc */
  function listen(doc) {
    const view = doc.defaultView;
    if (listening.has(doc)) {
      return;
    }
    // The open menus the last press went down in, until its click or a key. Its click is
    // theirs wherever it lands: a drag from a field in a menu to outside it clicks on an
    // ancestor of both. So is the focus it moves: WebKit, the macOS app's engine, focuses no
    // button on a press, and gives focus to the nearest ancestor a press can focus instead,
    // which for every menu in a view is the preview pane (`tabindex="-1"`). Closing on that
    // rebuilt the menu under the press, so its click never reached the row (mb-iwfs).
    /** @type {Set<OpenMenu>} */
    let pressedIn = new Set();
    // A press, a click an assistive technology sends with no press, or focus arriving
    // outside a menu and its trigger closes it. Captured, so no handler below can keep it
    // from here; the event goes on to what it landed on.
    /** @param {Event} event */
    const outside = (event) => {
      const node = /** @type {Node} */ (event.target);
      const held = event.type === "pointerdown" ? null : pressedIn;
      if (event.type !== "focusin") {
        pressedIn = new Set();
      }
      for (const entry of openMenusOf(doc)) {
        const own = triggerOf(entry.menu)?.contains(node) || entry.menu.inside(node);
        if (own && event.type === "pointerdown") {
          pressedIn.add(entry);
        } else if (!own && !held?.has(entry)) {
          closeMenu(entry, event.type === "focusin" ? "away" : "outside");
        }
      }
      unlisten(doc);
    };
    // Escape closes the menu opened last. One a surface above it took first is that
    // surface's ("Shared Overlay Lifecycle"), and a chord is the browser's and the app's.
    /** @param {Event} event */
    const onEscape = (event) => {
      const key = /** @type {KeyboardEvent} */ (event);
      // Focus a key moves is the key's, never a press's: a press let go with no click, as
      // one dragged off a row that was rebuilt, must not keep Tab from closing its menu.
      pressedIn = new Set();
      const last = openMenusOf(doc).at(-1);
      if (
        last &&
        key.key === "Escape" &&
        !(key.defaultPrevented || key.altKey || key.ctrlKey || key.metaKey)
      ) {
        key.preventDefault();
        closeMenu(last, "escape");
      }
      unlisten(doc);
    };
    // The window losing focus, to another application or to a frame in the page, whose
    // presses never reach this document, closes every menu.
    /** @param {Event} event */
    const blur = (event) => {
      for (const entry of event.target === view ? openMenusOf(doc) : []) {
        closeMenu(entry, "away");
      }
    };
    /** @type {Array<[string, EventListener, boolean]>} */
    const on = [
      ["pointerdown", outside, true],
      ["click", outside, true],
      ["focusin", outside, true],
      ["keydown", onEscape, false],
    ];
    for (const [type, listener, capture] of on) {
      doc.addEventListener(type, listener, capture);
    }
    view?.addEventListener("blur", blur);
    listening.set(doc, () => {
      for (const [type, listener, capture] of on) {
        doc.removeEventListener(type, listener, capture);
      }
      view?.removeEventListener("blur", blur);
    });
  }

  /** Let `doc`'s listeners go once none of its menus is open. @param {Document} doc */
  function unlisten(doc) {
    if (openMenusOf(doc).length === 0) {
      listening.get(doc)?.();
      listening.delete(doc);
    }
  }

  /**
   * Give one menu the closing every menu has. Call `opened()` each time it opens, from
   * every path that opens it, `closed()` when its own code closes it, and `dispose()` when
   * it goes for good. `name` is its surface's class, as tests/test_menu_dismissal.py
   * reads it.
   * @param {MetabrowserDismissibleMenu} menu
   * @returns {MetabrowserDismissibleHandle}
   */
  function dismissible(menu) {
    /** @type {OpenMenu | null} */
    let entry = null;
    const release = () => {
      if (entry) {
        openMenus.delete(entry);
        unlisten(entry.doc);
        entry = null;
      }
    };
    return Object.freeze({
      opened() {
        const doc = triggerOf(menu)?.ownerDocument;
        if (!doc || (entry && openMenus.has(entry))) {
          return;
        }
        // A menu another holder has open is that holder's, by its trigger: a container
        // bound around a bound control finds the control's dropdown drawn open, as a
        // diff's Markdown layer finds the File type menu in the diff it binds, and
        // opening it again here closed it under the reader at each mount (mb-iwfs).
        const trigger = triggerOf(menu);
        if (openMenusOf(doc).some((other) => triggerOf(other.menu) === trigger)) {
          return;
        }
        for (const other of openMenusOf(doc)) {
          closeMenu(other, "other");
        }
        entry = { menu, doc };
        openMenus.add(entry);
        listen(doc);
        // Focus goes with the menu. A press in WebKit gives a trigger none, and a rebuild
        // that put focus back on a tree row, say, would arrive outside and close the menu.
        const active = doc.activeElement;
        if (
          trigger?.isConnected &&
          !(active && (trigger.contains(active) || menu.inside(active)))
        ) {
          trigger.focus({ preventScroll: true });
        }
      },
      closed: release,
      dispose: release,
    });
  }

  global.MetabrowserMenus = Object.freeze({ dismissible });
})(window);
