// Generic file-preview composition shared by the shell and browserless sessions.

(() => {
  if (window.MetabrowserViewComposition) {
    return;
  }

  /**
   * @param {Array<() => void>} disposers
   * @param {(error: unknown) => void} onError
   */
  function disposeAll(disposers, onError) {
    for (const dispose of disposers) {
      try {
        dispose();
      } catch (error) {
        onError(error);
      }
    }
  }

  /**
   * Release every plugin key attached to an element inside `container`, the net under a
   * view's own `dispose()`: through the plugin shortcut facade once it has loaded, and
   * before then in the SDK's queue, which holds every key attached until it loads.
   *
   * @param {HTMLElement} container
   */
  function releaseShortcutsWithin(container) {
    const facade = window.MetabrowserPluginShortcuts;
    if (facade) {
      facade.releaseWithin(container);
      return;
    }
    const Node = window.Node;
    const queue = window.MetabrowserPluginHost?.shortcutQueue ?? new Set();
    for (const queued of queue) {
      // What the plugin passed is checked only when the facade takes it.
      if (typeof Node === "function" && queued.element instanceof Node) {
        if (container.contains(queued.element)) {
          // The queue lets go of the element as well as the key.
          queue.delete(queued);
        }
      }
    }
  }

  /**
   * Own the transfer from a staged preview to the active preview.
   *
   * A stage may be cancelled before commit. Once committed, its disposer list
   * stays live so a lazily mounted tab can join the active lifecycle later.
   *
   * @param {{onDisposeError?: (error: unknown) => void}=} options
   */
  function createLifecycle(options = {}) {
    const onDisposeError = options.onDisposeError ?? ((error) => console.error(error));
    /** @type {Array<() => void>} */
    let activeDisposers = [];

    return Object.freeze({
      begin() {
        /** @type {Array<() => void>} */
        const disposers = [];
        /** @type {"staged" | "installed" | "cancelled"} */
        let state = "staged";
        return Object.freeze({
          disposers,
          cancel() {
            if (state !== "staged") {
              return false;
            }
            state = "cancelled";
            disposeAll(disposers, onDisposeError);
            return true;
          },
          /** @param {() => void} replace */
          commit(replace) {
            if (state !== "staged") {
              return false;
            }
            const previous = activeDisposers;
            activeDisposers = [];
            disposeAll(previous, onDisposeError);
            try {
              replace();
            } catch (error) {
              state = "cancelled";
              disposeAll(disposers, onDisposeError);
              throw error;
            }
            activeDisposers = disposers;
            state = "installed";
            return true;
          },
        });
      },
      disposeActive() {
        const previous = activeDisposers;
        activeDisposers = [];
        disposeAll(previous, onDisposeError);
      },
    });
  }

  /**
   * Resolve the server's ordered view descriptors only after this kind's
   * manifest-owned assets have settled.
   *
   * @param {{
   *   kind: string,
   *   views: Array<MetabrowserPublicViewDescriptor>,
   *   preferredViewId?: string,
   *   ensureKindAssets: (kind: string) => Promise<void>,
   *   getRegisteredView: (kind: string, viewId: string) => MetabrowserPublicViewSpec | null | undefined,
   *   isCurrent?: () => boolean,
   * }} options
   * @returns {Promise<MetabrowserPublicPreparedViewComposition>}
   */
  async function prepare(options) {
    if (!options || typeof options.kind !== "string" || !options.kind) {
      throw new TypeError("view composition requires a non-empty kind");
    }
    if (!Array.isArray(options.views)) {
      throw new TypeError("view composition requires an ordered view list");
    }
    await options.ensureKindAssets(options.kind);
    if (options.isCurrent && !options.isCurrent()) {
      return Object.freeze({ initialView: null, status: "cancelled", views: [] });
    }
    const initialView =
      options.views.find((view) => view.id === options.preferredViewId) ??
      options.views.find((view) => view.default) ??
      options.views[0] ??
      null;
    const views = options.views.map((view) =>
      Object.freeze({
        renderer: options.getRegisteredView(options.kind, view.id) ?? null,
        view,
      }),
    );
    return Object.freeze({ initialView, status: "ready", views: Object.freeze(views) });
  }

  /**
   * Mount one registered renderer and bind its handle to a staged or active
   * lifecycle. A cancellation owns a late async handle, while a render failure
   * produces the shell's deterministic accessible error state.
   *
   * @param {HTMLElement} container
   * @param {MetabrowserPublicViewSpec} renderer
   * @param {MetabrowserPublicRenderContext} context
   * @param {Array<() => void>} disposers
   * @param {{
   *   afterMount?: (container: HTMLElement) => void,
   *   onError?: (error: unknown) => void,
   *   renderError?: (container: HTMLElement, error: unknown) => void,
   * }=} options
   * @returns {Promise<"mounted" | "cancelled" | "error">}
   */
  async function mount(container, renderer, context, disposers, options = {}) {
    /** @type {{disposed: boolean, handle: {dispose?: () => void, ready?: Promise<void>} | null}} */
    const record = { disposed: false, handle: null };
    disposers.push(() => {
      if (record.disposed) {
        return;
      }
      record.disposed = true;
      // The net runs before the view's own dispose, which may take its DOM, and the keys
      // attached inside it, out of the container. Detaching twice is harmless.
      releaseShortcutsWithin(container);
      if (typeof record.handle?.dispose === "function") {
        record.handle.dispose();
      }
      if (typeof renderer.dispose === "function") {
        renderer.dispose(container);
      }
    });
    try {
      const rendered = await Promise.resolve(renderer.render(container, context));
      const handle =
        rendered && typeof rendered === "object"
          ? /** @type {{dispose?: () => void, ready?: Promise<void>}} */ (rendered)
          : null;
      if (record.disposed) {
        // Rendered after the net ran: it is cast again over what this render attached.
        releaseShortcutsWithin(container);
        handle?.dispose?.();
        return "cancelled";
      }
      record.handle = handle;
      if (handle?.ready) {
        await handle.ready;
      }
      if (record.disposed) {
        return "cancelled";
      }
      options.afterMount?.(container);
      return "mounted";
    } catch (error) {
      // A render that failed may have attached keys first, and the error state below
      // takes its DOM out of the container, past the net.
      releaseShortcutsWithin(container);
      if (record.disposed) {
        return "cancelled";
      }
      options.onError?.(error);
      if (options.renderError) {
        options.renderError(container, error);
      } else {
        container.innerHTML =
          '<div class="preview-empty" role="alert">Could not display this view. Refresh the page to try again.</div>';
      }
      return "error";
    }
  }

  // A staged view is shown once the faces its text is set in have landed, at most
  // FACE_WAIT_MS later. Cold, PT Serif landed 13-30 ms after layout and, swapped in after
  // the stage was shown, moved the body 21-23 px (Chrome 152, load average 20-28).
  //
  // The faces are asked for by name, not inferred from `document.fonts.status`. A face is
  // requested only when layout reaches text set in it, and a renderer that writes its DOM
  // without yielding leaves the stage unlaid when the wait runs: the status still read
  // "loaded" there, and the face was requested 4-19 ms after the stage was shown.
  // Reading a computed style recalculates style but lays nothing out, so the
  // stage is still laid out once, after it is shown. Nor does `check()` tell: it read true
  // for PT Serif while the face was unloaded and while it loaded, so the faces are loaded
  // outright, and `load()` answers a face already there in under 0.1 ms with no frame
  // between (Chrome 152).
  const FACE_WAIT_MS = 100;
  // One element of each kind whose face decides where a document's lines break: body
  // text, headings, emphasis, and code, read from every staged document, since a later
  // document can be the first to use a face: remembering the first document's faces left
  // an all-italic document after a plain one to swap faces after it was shown (layout
  // shift 0.150). One of each, and a face the document does not use is not fetched.
  //
  // Reading them recalculates the whole stage's style, which is recalculated again once
  // it is moved into the pane: on a staged document of 2,717 elements with no frame
  // before the read, it took 33-38 ms and made the commit to its frame 69-88 ms against
  // 37-42 (Chrome 152). So once a stage has found a face missing, every face the page
  // declares is loaded at idle; then all of them are there, and no later stage reads a
  // style or waits.
  const FACE_SAMPLES = ["p", "h1, h2, h3, h4, h5, h6", "strong, b", "em, i", "code, pre", "li"];
  // The text a face is loaded for. Without it the engine loads for a space, which the
  // prose stack's first family, a local face for quotation marks, does not cover either,
  // and a face split by unicode-range is chosen by the characters it is for.
  const FACE_SAMPLE_TEXT = "Aa";
  let declaredFacesQueued = false;

  /** @param {FontFaceSet} fonts Load, at idle, every declared face not yet asked for. */
  function loadDeclaredFaces(fonts) {
    if (declaredFacesQueued) {
      return;
    }
    declaredFacesQueued = true;
    const run = () => {
      declaredFacesQueued = false;
      for (const face of fonts) {
        if (face.status === "unloaded") {
          face.load().catch(() => {});
        }
      }
    };
    if (typeof requestIdleCallback === "function") {
      requestIdleCallback(run, { timeout: 2000 });
    } else {
      setTimeout(run, 1000);
    }
  }

  /**
   * Wait, briefly, for the faces a staged document's text is set in.
   *
   * @param {Element | null | undefined} root
   * @returns {Promise<void> | null} `null` when every face the page declares is there.
   */
  function settleFaces(root) {
    const fonts = typeof document === "undefined" ? undefined : document.fonts;
    if (!root || typeof fonts?.load !== "function") {
      return null;
    }
    // A face that failed to load is as settled as one that loaded.
    if (
      Array.from(fonts, (face) => face.status).every(
        (status) => status === "loaded" || status === "error",
      )
    ) {
      return null;
    }
    /** @type {Set<string>} */
    const wanted = new Set();
    for (const element of [root, ...FACE_SAMPLES.map((selector) => root.querySelector(selector))]) {
      if (element) {
        const style = getComputedStyle(element);
        // The size in the `font` shorthand chooses no face; the family list, weight, and
        // style do.
        wanted.add(`${style.fontStyle} ${style.fontWeight} 16px ${style.fontFamily}`);
      }
    }
    loadDeclaredFaces(fonts);
    /** @type {ReturnType<typeof setTimeout> | undefined} */
    let timer;
    const capped = new Promise((resolve) => {
      timer = setTimeout(resolve, FACE_WAIT_MS);
    });
    const landed = Promise.all(
      Array.from(wanted, (font) => {
        try {
          // A face that fails to load, or a family this engine cannot parse back, is
          // not one to wait for.
          return fonts.load(font, FACE_SAMPLE_TEXT).catch(() => []);
        } catch {
          return [];
        }
      }),
    );
    return Promise.race([landed, capped]).then(() => {
      clearTimeout(timer);
    });
  }

  window.MetabrowserViewComposition = Object.freeze({
    FACE_WAIT_MS,
    createLifecycle,
    mount,
    prepare,
    settleFaces,
  });
})();
