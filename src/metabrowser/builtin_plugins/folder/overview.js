/** @typedef {{key: string, data: unknown} | null} PanelResolution */
/** @typedef {{dispose: () => void, update?: (context: {path?: string, raw?: unknown}, data: unknown) => void | Promise<void>}} PanelHandle */
/** @typedef {{id: string, label: string, placement: "summary" | "content" | "supplemental", presentation: "surface" | "document", printable?: boolean, required?: boolean, classifyError?: (error: unknown) => {message: string, retryable: boolean}, resolve: (context: {path?: string, raw?: unknown}, options: {signal: AbortSignal}) => PanelResolution | Promise<PanelResolution>, mount: (container: HTMLElement, context: {path?: string, raw?: unknown}, data: unknown, options: {signal?: AbortSignal}) => void | PanelHandle | Promise<void | PanelHandle>}} PanelDescriptor */
/** @typedef {{descriptor: PanelDescriptor, slot: HTMLElement, body: HTMLElement, generation: number, resolveController: AbortController | null, mountController: AbortController | null, handle: PanelHandle | null, key: string | null, retry: (() => void) | null, mounted: boolean}} PanelRecord */
/** @typedef {{listPanels: () => ReadonlyArray<PanelDescriptor>}} PanelRegistry */

/** @param {PanelDescriptor} descriptor */
export function createPanelSlot(descriptor) {
  const slot = document.createElement("section");
  slot.className = `folder-overview-panel folder-overview-panel-${descriptor.presentation}`;
  slot.dataset.panelId = descriptor.id;
  slot.setAttribute("aria-label", descriptor.label);
  slot.hidden = false;
  const heading = document.createElement("h2");
  heading.className = "folder-overview-panel-heading";
  heading.textContent = descriptor.label;
  const body = document.createElement("div");
  body.className = "folder-overview-panel-body";
  slot.append(heading, body);
  return { body, slot };
}

/** @param {HTMLElement} container @param {Array<PanelRecord>} records @param {MetabrowserPublicSdk} mb */
export function publishPrintState(container, records, mb) {
  const printable = records.some((record) => record.mounted && record.descriptor.printable);
  mb.setViewPrintState(container, {
    printable,
    profile: printable ? "document" : "plain",
    runtime: printable ? "kpress" : undefined,
  });
}

/**
 * @param {HTMLElement} container
 * @param {{path?: string, raw?: unknown}} initialContext
 * @param {MetabrowserPublicSdk} mb
 * @param {PanelRegistry} registry
 */
export function mountOverview(container, initialContext, mb, registry) {
  container.innerHTML = "";
  const stack = document.createElement("div");
  stack.className = "folder-overview-stack";
  container.append(stack);
  let disposed = false;
  let active = mb.viewState.isActive(container);
  let stale = false;
  let context = initialContext;

  /** @type {Array<PanelRecord>} */
  const records = registry.listPanels().map((descriptor) => {
    const elements = createPanelSlot(descriptor);
    elements.body.innerHTML = '<div class="folder-overview-loading" aria-hidden="true"></div>';
    stack.append(elements.slot);
    return {
      descriptor,
      slot: elements.slot,
      body: elements.body,
      generation: 0,
      resolveController: null,
      mountController: null,
      handle: null,
      key: null,
      retry: null,
      mounted: false,
    };
  });

  /** @param {PanelRecord} record */
  function disposeMount(record) {
    record.mountController?.abort();
    record.mountController = null;
    if (record.handle) {
      const handle = record.handle;
      record.handle = null;
      handle.dispose();
    }
    record.mounted = false;
  }

  /** @param {PanelRecord} record @param {unknown} error */
  function renderFailure(record, error) {
    if (mb.errors.isAbortError(error) || disposed) {
      return;
    }
    const classification = record.descriptor.classifyError
      ? record.descriptor.classifyError(error)
      : mb.errors.classifyRequestError(error);
    record.body.replaceChildren();
    const failure = document.createElement("div");
    failure.className = "folder-overview-panel-error";
    failure.setAttribute("role", "alert");
    const message = document.createElement("span");
    message.textContent = classification.message;
    failure.append(message);
    if (classification.retryable) {
      const retry = document.createElement("button");
      retry.type = "button";
      retry.textContent = "Retry";
      const listener = () => void resolvePanel(record);
      retry.addEventListener("click", listener);
      record.retry = () => retry.removeEventListener("click", listener);
      failure.append(retry);
    }
    record.body.append(failure);
    record.slot.hidden = false;
    publishPrintState(container, records, mb);
  }

  /** @param {PanelRecord} record @param {PanelResolution} result @param {number} generation */
  async function applyResolution(record, result, generation) {
    if (disposed || generation !== record.generation) {
      return;
    }
    record.retry?.();
    record.retry = null;
    if (result === null) {
      if (record.descriptor.required) {
        disposeMount(record);
        record.key = null;
        renderFailure(record, new Error("A required Overview panel returned no content."));
      } else {
        disposeMount(record);
        record.key = null;
        record.slot.hidden = true;
      }
      publishPrintState(container, records, mb);
      return;
    }
    record.slot.hidden = false;
    if (record.mounted && record.key === result.key) {
      try {
        await record.handle?.update?.(context, result.data);
      } catch (error) {
        disposeMount(record);
        record.key = null;
        throw error;
      }
      return;
    }
    disposeMount(record);
    record.body.replaceChildren();
    record.key = result.key;
    const mountController = new AbortController();
    record.mountController = mountController;
    try {
      const handle = await record.descriptor.mount(record.body, context, result.data, {
        signal: mountController.signal,
      });
      if (disposed || generation !== record.generation) {
        mountController.abort();
        handle?.dispose();
        if (record.mountController === mountController) {
          record.mountController = null;
        }
        return;
      }
      record.handle = handle || { dispose() {} };
      record.mounted = true;
      publishPrintState(container, records, mb);
    } catch (error) {
      mountController.abort();
      if (record.mountController === mountController) {
        record.mountController = null;
      }
      if (disposed || generation !== record.generation) {
        return;
      }
      renderFailure(record, error);
    }
  }

  /** @param {PanelRecord} record */
  async function resolvePanel(record) {
    record.resolveController?.abort();
    const resolveController = new AbortController();
    record.resolveController = resolveController;
    const generation = ++record.generation;
    try {
      const result = await record.descriptor.resolve(context, {
        signal: resolveController.signal,
      });
      await applyResolution(record, result, generation);
    } catch (error) {
      if (generation === record.generation) {
        renderFailure(record, error);
      }
    }
  }

  function reconcile() {
    stale = false;
    for (const record of records) {
      void resolvePanel(record);
    }
  }

  const unsubscribeContext = mb.folderContext.subscribe(initialContext.path || "", (envelope) => {
    context = { ...context, path: envelope.path, raw: envelope };
    if (active) {
      reconcile();
    } else {
      stale = true;
    }
  });
  const unsubscribeActive = mb.viewState.subscribeActive(container, (nextActive) => {
    active = nextActive;
    if (active && stale) {
      reconcile();
    }
  });
  if (active && records.every((record) => record.generation === 0)) {
    reconcile();
  }

  publishPrintState(container, records, mb);
  return Object.freeze({
    dispose() {
      if (disposed) {
        return;
      }
      disposed = true;
      unsubscribeActive();
      unsubscribeContext();
      for (const record of [...records].reverse()) {
        record.resolveController?.abort();
        record.retry?.();
        disposeMount(record);
      }
      mb.setViewPrintState(container, { printable: false, profile: "plain" });
    },
  });
}

/** @param {MetabrowserPublicSdk} mb @param {PanelRegistry} registry */
export function createOverviewView(mb, registry) {
  return Object.freeze({
    /** @param {HTMLElement} container @param {{path?: string, raw?: unknown}} context */
    render: (container, context) => mountOverview(container, context, mb, registry),
  });
}
