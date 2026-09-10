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

  window.MetabrowserViewComposition = Object.freeze({ createLifecycle, mount, prepare });
})();
