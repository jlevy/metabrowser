// A multi-file diff's File type filter: which of a comparison's changed files it shows.
//
// Which files a choice keeps is the comparison route's (`types=`), and the counts its
// menu lists are the route's too (`view=types`), so `metab` answers both. This module is
// the state between them: the choice, the one request for it, the diff that answer mounts,
// and the menu, which is the Files tab's File type menu (`filterControls.typeMenu`). The
// whole comparison stays in hand, so going back to every type asks for nothing.
//
// The choice belongs to the page and is never kept: a reload, or another comparison,
// starts with every type.

/** @typedef {Record<string, unknown>} DiffDocument */

/**
 * What a mounted diff gives its host, which the filter passes through to whichever diff
 * is mounted now: a host holds one handle while the files under it change.
 *
 * @typedef {{
 *   scrollToFile: (path: string) => unknown,
 *   fileForPath: (path: string) => unknown,
 *   sectionForPath: (path: string) => unknown,
 *   pathForSection: (section: Element) => unknown,
 *   currentFile: () => unknown,
 *   firstScreen: () => Promise<unknown>,
 *   onCurrentFile: (listener: (file: unknown) => void) => () => void,
 *   cancelPending: () => void,
 *   dispose: () => void,
 * }} DiffHandle
 */

/**
 * What the toolbar control draws.
 *
 * @typedef {{
 *   types: Array<string> | null,
 *   tally: MetabrowserPublicTypeTally | null,
 *   loading: boolean,
 *   failed: boolean,
 *   kept: number | null,
 *   whole: number,
 * }} TypeFilterState
 */

/** What the diff says while the files of the chosen types are none. */
export const NONE_KEPT = "No changed file is of the chosen types.";

/** What the toolbar says when the narrowed comparison did not load. */
export const LOAD_FAILED = "Could not load the files of these types.";

/**
 * The `types` parameter for a choice, or null for every type. Sorted, so one set of
 * types is one address and one cached answer, whatever order it was picked in.
 *
 * @param {ReadonlyArray<string> | null} types
 * @returns {string | null}
 */
export function typesParam(types) {
  if (types === null || types.length === 0) {
    return null;
  }
  return [...new Set(types)].sort().join(",");
}

/**
 * "12 of 35 files": how many of the comparison's files the choice keeps.
 *
 * @param {number} kept
 * @param {number} whole
 * @param {(value: number) => string} formatInteger
 */
export function narrowedNote(kept, whole, formatInteger) {
  return `${formatInteger(kept)} of ${formatInteger(whole)} ${whole === 1 ? "file" : "files"}`;
}

/**
 * How many files a document's totals count, or null where it says none.
 *
 * @param {DiffDocument} document_
 * @returns {number | null}
 */
function filesOf(document_) {
  const manifest = /** @type {{totals?: {files?: unknown}} | undefined} */ (document_.manifest);
  const files = manifest?.totals?.files;
  return typeof files === "number" ? files : null;
}

/**
 * The change in *document_* at *path*, on either side, or null.
 *
 * @param {DiffDocument} document_
 * @param {string} path
 * @returns {Record<string, unknown> | null}
 */
function changeAt(document_, path) {
  const manifest = /** @type {{files?: Array<Record<string, unknown>>} | undefined} */ (
    document_.manifest
  );
  for (const change of manifest?.files ?? []) {
    const sides = /** @type {Array<{path?: unknown} | null | undefined>} */ ([
      change.new,
      change.old,
    ]);
    if (sides.some((side) => side?.path === path)) {
      return change;
    }
  }
  return null;
}

/**
 * The filter's state machine. It mounts *whole*, or the *initial* choice's answer, asks for
 * the counts, and on each choice asks for that choice's comparison, dropping an answer a
 * later choice overtook, and mounts it in place of the diff before it. Every choice paints
 * at once, so the menu shows it while its files load, and is told to *changed*.
 *
 * A jump to a file the choice hides, from the Diff summary or a host's list of files, goes
 * back to every type and then to the file: a jump is the reader asking to see that file,
 * and the whole comparison is in hand, so it costs no request. A lookup answers for the
 * whole comparison for the same reason.
 *
 * @param {{
 *   whole: DiffDocument,
 *   wholeFiles?: number | null,
 *   initial?: {types: Array<string>, document: DiffDocument} | null,
 *   load: (types: string, signal: AbortSignal) => Promise<DiffDocument>,
 *   counts: (signal: AbortSignal) => Promise<MetabrowserPublicTypeTally>,
 *   mount: (document_: DiffDocument, narrowed: {kept: number, whole: number} | null) => DiffHandle,
 *   paint: (state: TypeFilterState) => void,
 *   swap?: (change: () => void) => void,
 *   changed?: (types: Array<string> | null) => void,
 *   report?: (what: "counts" | "files", error: unknown) => void,
 * }} deps
 *   *wholeFiles* is how many files the whole comparison changes where its list is cut
 *   short; otherwise the whole document's totals say it.
 *   *initial* is a choice the host kept, as a pull request's page keeps it while the reader
 *   is on another tab, with its answer, which mounts first.
 *   *swap* runs each replacement of the mounted diff, which moves the toolbar control into
 *   the new diff, so a host can keep focus where it was.
 */
export function createTypeFilter(deps) {
  const whole = deps.wholeFiles ?? filesOf(deps.whole) ?? 0;
  const initial = deps.initial ?? null;
  const initialTypes = initial === null ? null : typesParam(initial.types);
  /** @type {TypeFilterState} */
  const state = {
    types: initialTypes === null ? null : initialTypes.split(","),
    tally: null,
    loading: false,
    failed: false,
    kept: initial === null || initialTypes === null ? null : (filesOf(initial.document) ?? 0),
    whole,
  };
  let disposed = false;
  /** @type {AbortController | null} */
  let pending = null;
  const countsController = new AbortController();
  /** @type {Map<(file: unknown) => void, () => void>} */
  const listeners = new Map();
  let current =
    initial === null || state.kept === null
      ? deps.mount(deps.whole, null)
      : deps.mount(initial.document, { kept: state.kept, whole });

  const paint = () => {
    if (!disposed) {
      deps.paint({ ...state });
    }
  };

  /**
   * @param {DiffDocument} document_
   * @param {{kept: number, whole: number} | null} narrowed
   */
  function remount(document_, narrowed) {
    for (const unsubscribe of listeners.values()) {
      unsubscribe();
    }
    const swap = deps.swap ?? ((change) => change());
    swap(() => {
      current.dispose();
      current = deps.mount(document_, narrowed);
    });
    for (const listener of listeners.keys()) {
      listeners.set(listener, current.onCurrentFile(listener));
    }
  }

  /** @param {ReadonlyArray<string> | null} next */
  async function select(next) {
    const param = typesParam(next);
    // The same choice again does nothing, unless its files did not load: then it asks again.
    if (disposed || (param === typesParam(state.types) && !state.failed)) {
      return;
    }
    pending?.abort();
    pending = null;
    state.types = param === null ? null : param.split(",");
    deps.changed?.(state.types === null ? null : state.types.slice());
    state.failed = false;
    if (param === null) {
      state.loading = false;
      state.kept = null;
      paint();
      remount(deps.whole, null);
      return;
    }
    const controller = new AbortController();
    pending = controller;
    state.loading = true;
    paint();
    try {
      const document_ = await deps.load(param, controller.signal);
      if (controller.signal.aborted || disposed) {
        return;
      }
      pending = null;
      state.loading = false;
      state.kept = filesOf(document_) ?? 0;
      remount(document_, { kept: state.kept, whole });
    } catch (error) {
      if (controller.signal.aborted || disposed) {
        return;
      }
      pending = null;
      state.loading = false;
      state.failed = true;
      deps.report?.("files", error);
    }
    paint();
  }

  /**
   * Whether the choice hides *path*: the whole comparison changes it, and the diff mounted
   * now does not show it.
   *
   * @param {string} path
   */
  function hidden(path) {
    const lookup = /** @type {{kind?: unknown}} */ (current.fileForPath(path));
    return lookup.kind !== "file" && changeAt(deps.whole, path) !== null;
  }

  deps.counts(countsController.signal).then(
    (tally) => {
      if (!disposed) {
        state.tally = tally;
        paint();
      }
    },
    (error) => {
      if (!countsController.signal.aborted) {
        deps.report?.("counts", error);
      }
    },
  );
  paint();

  return {
    /** @param {ReadonlyArray<string> | null} types */
    select,
    clear: () => select(null),
    /** The choice now, null for every type. */
    types: () => (state.types === null ? null : state.types.slice()),
    /** The handle of the diff mounted now; a host's calls go to it. */
    handle: () => current,
    /** @type {DiffHandle} */
    facade: {
      scrollToFile(path) {
        if (state.types !== null && !disposed && hidden(path)) {
          void select(null);
        }
        return current.scrollToFile(path);
      },
      fileForPath(path) {
        const change = disposed || !hidden(path) ? null : changeAt(deps.whole, path);
        if (change === null) {
          return current.fileForPath(path);
        }
        return {
          kind: "file",
          path,
          fileId: String(change.id),
          changeKind: String(change.kind),
          availability: String(change.availability),
        };
      },
      // A host keeps a reader's place in its file, whichever diff shows it (mb-riqt): it
      // asks the diff mounted now where that file's section is, and whose a section is.
      sectionForPath: (path) => current.sectionForPath(path),
      pathForSection: (section) => current.pathForSection(section),
      currentFile: () => current.currentFile(),
      firstScreen: () => current.firstScreen(),
      onCurrentFile(listener) {
        if (disposed) {
          return () => {};
        }
        listeners.set(listener, current.onCurrentFile(listener));
        return () => {
          listeners.get(listener)?.();
          listeners.delete(listener);
        };
      },
      cancelPending: () => current.cancelPending(),
      dispose() {
        if (disposed) {
          return;
        }
        disposed = true;
        pending?.abort();
        countsController.abort();
        listeners.clear();
        current.dispose();
      },
    },
  };
}

let menuIds = 0;

/**
 * The toolbar's File type control: the Files tab's menu, the note of how many files it
 * keeps, and Clear. It draws a filter's state into *element*, which the diff's toolbar
 * holds before its layout control; each diff the filter mounts takes the same element.
 * `Y` opens the menu, through the SDK's shortcut surface.
 *
 * @param {HTMLElement} element
 * @param {NonNullable<MetabrowserPublicSdk["filterControls"]>} fc
 * @param {{
 *   select: (types: Array<string> | null) => unknown,
 *   formatInteger: (value: number) => string,
 *   shortcuts?: MetabrowserPublicSdk["shortcuts"],
 * }} host
 */
export function createTypeFilterControl(element, fc, host) {
  const menuId = `diff-type-menu-${++menuIds}`;
  let open = false;
  /** @type {TypeFilterState | null} */
  let drawn = null;
  /** @type {MetabrowserPublicPluginShortcutHandle | null} */
  let key = null;
  element.className = "diff-type-control";

  const trigger = () =>
    /** @type {HTMLElement | null} */ (element.querySelector("[data-chip-menu-toggle]"));

  /** @param {TypeFilterState} state */
  function paint(state) {
    drawn = state;
    const tally = state.tally ?? {};
    const restore = fc.keepFocus(element);
    const note = state.failed
      ? LOAD_FAILED
      : state.kept !== null
        ? narrowedNote(state.kept, state.whole, host.formatInteger)
        : "";
    element.innerHTML =
      fc.menuGroupHtml({
        key: "types",
        label: "File type",
        options: fc.typeMenu.options(tally),
        presetSections: fc.typeMenu.presetSections(tally),
        value: state.types,
        anyLabel: "Any type",
        open,
        menuId,
      }) +
      (note === ""
        ? ""
        : state.failed
          ? // A failed load is an error notice, which interrupts a screen reader.
            `<span class="notice diff-type-note" data-severity="error" role="alert">` +
            `${fc.escapeHtml(note)}</span>`
          : `<span class="diff-type-note">${fc.escapeHtml(note)}</span>`) +
      (state.types === null ? "" : fc.clearHtml({ label: "Clear" }));
    element.setAttribute("aria-busy", state.loading ? "true" : "false");
    restore();
    const target = trigger();
    if (key !== null && target !== null) {
      key.retarget(target);
    }
  }

  const repaint = () => {
    if (drawn !== null) {
      paint(drawn);
    }
  };

  /** Open the menu with its checked row focused, as its trigger's click does: `Y`. */
  function openMenu() {
    open = true;
    repaint();
    fc.focusMenu(element, "types");
  }

  /** @param {string} presetId */
  function presetValues(presetId) {
    for (const section of fc.typeMenu.presetSections(drawn?.tally ?? {})) {
      const preset = section.presets.find((candidate) => candidate.id === presetId);
      if (preset) {
        return preset.values;
      }
    }
    return null;
  }

  const unbind = fc.bind(element, {
    onMenuToggle(_key, isOpen) {
      open = isOpen;
      repaint();
    },
    onMenuPick(_key, value) {
      // Multi-select stays open: picking several types is the point of it.
      const types = drawn?.types ?? null;
      host.select(value === null ? null : toList(fc.nextSelection("many", types, value)));
    },
    onMenuPreset(_key, presetId, wasOn) {
      const values = presetValues(presetId);
      if (values !== null) {
        host.select(fc.typeMenu.togglePreset(drawn?.types ?? null, values, wasOn));
      }
    },
    onClear() {
      open = false;
      host.select(null);
      // Clear is gone once nothing is chosen, so focus goes to the menu it reset.
      trigger()?.focus();
    },
  });

  return {
    paint,
    openMenu,
    /**
     * Run *change*, which moves this control into another diff's toolbar, keeping focus on
     * the control that had it: a move takes it out of the document, which drops focus.
     *
     * @param {() => void} change
     */
    swap(change) {
      const restore = fc.keepFocus(element);
      change();
      restore();
    },
    /** Attach `Y` once the control is in the page, on its trigger. */
    attachKey() {
      const target = trigger();
      if (key !== null || target === null || typeof host.shortcuts?.attach !== "function") {
        return;
      }
      key = host.shortcuts.attach(target, {
        activate: openMenu,
        copy: {
          action: "Choose file types",
          description: "Open the diff's File type menu.",
          hint: "File type",
        },
        group: "controls",
        id: "diff.type-filter",
        key: "y",
        order: 39,
      });
    },
    dispose() {
      key?.detach();
      key = null;
      unbind();
      element.replaceChildren();
    },
  };
}

/**
 * @param {string | Array<string> | null} selection
 * @returns {Array<string> | null}
 */
function toList(selection) {
  if (selection === null) {
    return null;
  }
  return Array.isArray(selection) ? selection : [selection];
}
