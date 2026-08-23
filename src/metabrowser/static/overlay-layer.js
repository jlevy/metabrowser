// Shared modal portal, focus, inert-background, and trigger lifecycle.

(() => {
  const FOCUSABLE_SELECTOR = [
    "a[href]",
    "button:not([disabled])",
    "input:not([disabled])",
    "select:not([disabled])",
    "textarea:not([disabled])",
    '[tabindex]:not([tabindex="-1"])',
  ].join(",");
  let dialogSerial = 0;
  /** @type {WeakMap<Document, ModalController>} */
  const activeModals = new WeakMap();

  /**
   * @typedef {object} BackgroundState
   * @property {HTMLElement} element
   * @property {boolean} inert
   */
  /**
   * @typedef {object} AttributeState
   * @property {boolean} present
   * @property {string | null} value
   */
  /**
   * @typedef {object} DialogShell
   * @property {HTMLElement} body
   * @property {HTMLButtonElement} closeButton
   * @property {HTMLElement} dialog
   * @property {HTMLElement} element
   * @property {HTMLElement} footer
   * @property {HTMLElement} title
   */
  /**
   * @typedef {object} ModalController
   * @property {HTMLElement} body
   * @property {() => void} dispose
   * @property {HTMLElement} dialog
   * @property {HTMLElement} element
   * @property {HTMLElement} footer
   * @property {HTMLElement} title
   * @property {HTMLButtonElement} closeButton
   * @property {Readonly<{connect: (element: HTMLElement) => () => void}>} control
   * @property {(options?: {restoreFocus?: boolean}) => void} close
   * @property {() => boolean} isOpen
   * @property {(trigger?: HTMLElement | null) => void} open
   */
  /**
   * @typedef {object} ShortcutRegistry
   * @property {(scope: string, options?: {exclusive?: boolean}) => () => void} activateScope
   * @property {(commandId: string, context?: Record<string, unknown>) => boolean} invoke
   * @property {(commandId: string) => null | {bindings: {ariaKeyshortcuts: string}, copy: {action: string}}} present
   */

  /** @param {unknown} value @returns {value is HTMLElement} */
  function focusable(value) {
    return Boolean(value && typeof (/** @type {{focus?: unknown}} */ (value).focus) === "function");
  }

  /** @param {unknown} value @returns {value is HTMLElement} */
  function connectedFocusable(value) {
    return focusable(value) && /** @type {HTMLElement} */ (value).isConnected;
  }

  /** @param {HTMLElement} root @returns {HTMLElement[]} */
  function focusableElements(root) {
    return Array.from(
      root.querySelectorAll(FOCUSABLE_SELECTOR),
      (candidate) => /** @type {HTMLElement} */ (candidate),
    ).filter((candidate) => {
      const element = /** @type {HTMLElement} */ (candidate);
      return (
        !element.hidden &&
        element.getAttribute("aria-hidden") !== "true" &&
        !(/** @type {HTMLButtonElement} */ (element).disabled) &&
        element.tabIndex >= 0
      );
    });
  }

  /** @param {Document} hostDocument @param {HTMLElement} portal */
  function captureBackgroundState(hostDocument, portal) {
    /** @type {BackgroundState[]} */
    const records = [];
    for (const child of hostDocument.body.children) {
      if (child === portal) {
        continue;
      }
      const element = /** @type {HTMLElement} */ (child);
      records.push({ element, inert: element.inert });
      element.inert = true;
    }
    return records;
  }

  /** @param {readonly BackgroundState[]} records */
  function restoreBackgroundState(records) {
    for (const record of records) {
      record.element.inert = record.inert;
    }
  }

  /** @param {HTMLElement} element @param {string} name */
  function captureAttribute(element, name) {
    return Object.freeze({
      present: element.hasAttribute(name),
      value: element.getAttribute(name),
    });
  }

  /** @param {HTMLElement} element @param {string} name @param {AttributeState} state */
  function restoreAttribute(element, name, state) {
    if (state.present) {
      element.setAttribute(name, state.value || "");
    } else {
      element.removeAttribute(name);
    }
  }

  /**
   * @param {{document: Document, title: string, className?: string}} options
   * @returns {DialogShell}
   */
  function createDialogShell(options) {
    dialogSerial += 1;
    const idPrefix = `metabrowser-dialog-${dialogSerial}`;
    const element = options.document.createElement("div");
    element.className = "modal-overlay";
    element.hidden = true;

    const dialog = options.document.createElement("section");
    dialog.className = ["modal-dialog", options.className || ""].filter(Boolean).join(" ");
    dialog.id = idPrefix;
    dialog.setAttribute("role", "dialog");
    dialog.setAttribute("aria-modal", "true");
    dialog.setAttribute("aria-labelledby", `${idPrefix}-title`);
    dialog.setAttribute("tabindex", "-1");

    const header = options.document.createElement("header");
    header.className = "modal-header";
    const title = options.document.createElement("h2");
    title.className = "modal-title";
    title.id = `${idPrefix}-title`;
    title.textContent = options.title;
    const closeButton = /** @type {HTMLButtonElement} */ (options.document.createElement("button"));
    closeButton.className = "btn modal-close";
    closeButton.setAttribute("type", "button");
    closeButton.textContent = "Close";
    header.append(title, closeButton);

    const body = options.document.createElement("div");
    body.className = "modal-body";
    const footer = options.document.createElement("footer");
    footer.className = "modal-footer";
    footer.hidden = true;
    dialog.append(header, body, footer);
    element.append(dialog);
    return Object.freeze({ body, closeButton, dialog, element, footer, title });
  }

  /**
   * @param {{
   *   className?: string,
   *   closeCommandId: string,
   *   document?: Document,
   *   initialFocus?: HTMLElement | (() => HTMLElement | null),
   *   onClose?: () => void,
   *   onOpen?: () => void,
   *   resolveFocusFallback?: (previous: HTMLElement | null) => HTMLElement | null,
   *   scope: string,
   *   shortcuts: ShortcutRegistry,
   *   title: string,
   * }} options
   * @returns {Readonly<ModalController>}
   */
  function createModal(options) {
    if (!options?.shortcuts || !options.closeCommandId || !options.scope || !options.title) {
      throw new TypeError("Modal requires shortcuts, a close command, a scope, and a title");
    }
    const hostDocument = options.document || window.document;
    if (!hostDocument?.body) {
      throw new Error("Modal requires a document body");
    }
    const closePresentation = options.shortcuts.present(options.closeCommandId);
    if (!closePresentation) {
      throw new TypeError(`Modal close command is not registered: ${options.closeCommandId}`);
    }
    const shell = createDialogShell({
      className: options.className,
      document: hostDocument,
      title: options.title,
    });
    shell.closeButton.setAttribute("aria-label", closePresentation.copy.action);
    if (closePresentation.bindings.ariaKeyshortcuts) {
      shell.closeButton.setAttribute(
        "aria-keyshortcuts",
        closePresentation.bindings.ariaKeyshortcuts,
      );
    }
    hostDocument.body.append(shell.element);

    /** @type {BackgroundState[]} */
    let backgroundState = [];
    /** @type {(() => void) | null} */
    let deactivateScope = null;
    /** @type {HTMLElement | null} */
    let openingTrigger = null;
    /** @type {HTMLElement | null} */
    let previousFocus = null;
    /** @type {Map<HTMLElement, {attributes: Record<string, AttributeState>}>} */
    const connectedControls = new Map();
    let disposed = false;

    function synchronizeControls() {
      for (const element of connectedControls.keys()) {
        element.setAttribute("aria-expanded", String(!shell.element.hidden));
      }
    }

    const control = Object.freeze({
      /** @param {HTMLElement} element */
      connect(element) {
        if (!focusable(element)) {
          throw new TypeError("Modal control requires an HTML element");
        }
        if (connectedControls.has(element)) {
          throw new Error("Modal control is already connected");
        }
        connectedControls.set(element, {
          attributes: {
            "aria-controls": captureAttribute(element, "aria-controls"),
            "aria-expanded": captureAttribute(element, "aria-expanded"),
            "aria-haspopup": captureAttribute(element, "aria-haspopup"),
          },
        });
        element.setAttribute("aria-controls", shell.dialog.id);
        element.setAttribute("aria-haspopup", "dialog");
        element.setAttribute("aria-expanded", String(!shell.element.hidden));
        let connected = true;
        return () => {
          if (!connected) {
            return;
          }
          connected = false;
          const record = connectedControls.get(element);
          connectedControls.delete(element);
          if (!record) {
            return;
          }
          for (const [name, state] of Object.entries(record.attributes)) {
            restoreAttribute(element, name, state);
          }
        };
      },
    });

    /** @param {HTMLElement | null} target */
    function restoreFocus(target) {
      if (connectedFocusable(target)) {
        target.focus();
        return;
      }
      const fallback = options.resolveFocusFallback?.(previousFocus) || null;
      if (connectedFocusable(fallback)) {
        fallback.focus();
      }
    }

    /** @param {{restoreFocus?: boolean}} [closeOptions] */
    function close(closeOptions = {}) {
      if (shell.element.hidden) {
        return;
      }
      const shouldRestoreFocus = closeOptions.restoreFocus !== false;
      shell.element.hidden = true;
      deactivateScope?.();
      deactivateScope = null;
      restoreBackgroundState(backgroundState);
      backgroundState = [];
      options.onClose?.();
      synchronizeControls();
      if (activeModals.get(hostDocument) === controller) {
        activeModals.delete(hostDocument);
      }
      const focusTarget = openingTrigger || previousFocus;
      openingTrigger = null;
      if (shouldRestoreFocus) {
        restoreFocus(focusTarget);
      }
      previousFocus = null;
    }

    /** @param {HTMLElement | null} [trigger] */
    function open(trigger = null) {
      if (disposed) {
        throw new Error("Modal is disposed");
      }
      if (!shell.element.hidden) {
        const target = resolveInitialFocus();
        target.focus();
        return;
      }
      const active = activeModals.get(hostDocument);
      if (active && active !== controller) {
        active.close({ restoreFocus: false });
      }
      previousFocus = focusable(hostDocument.activeElement)
        ? /** @type {HTMLElement} */ (hostDocument.activeElement)
        : null;
      openingTrigger = focusable(trigger) ? trigger : null;
      backgroundState = captureBackgroundState(hostDocument, shell.element);
      shell.element.hidden = false;
      deactivateScope = options.shortcuts.activateScope(options.scope, { exclusive: true });
      activeModals.set(hostDocument, controller);
      options.onOpen?.();
      synchronizeControls();
      resolveInitialFocus().focus();
    }

    function resolveInitialFocus() {
      const configured =
        typeof options.initialFocus === "function" ? options.initialFocus() : options.initialFocus;
      if (connectedFocusable(configured) && shell.dialog.contains(configured)) {
        return configured;
      }
      return shell.closeButton;
    }

    /** @param {KeyboardEvent} event */
    function handleDialogKeydown(event) {
      if (event.key !== "Tab") {
        return;
      }
      const values = focusableElements(shell.dialog);
      if (values.length === 0) {
        event.preventDefault();
        shell.dialog.focus();
        return;
      }
      const first = values[0];
      const last = values.at(-1);
      if (
        (event.shiftKey && hostDocument.activeElement === first) ||
        (!event.shiftKey && hostDocument.activeElement === last) ||
        !shell.dialog.contains(hostDocument.activeElement)
      ) {
        event.preventDefault();
        (event.shiftKey ? last : first)?.focus();
      }
    }

    /** @param {PointerEvent} event */
    function handleScrimPointerdown(event) {
      if (event.target === shell.element) {
        options.shortcuts.invoke(options.closeCommandId, { event });
      }
    }

    function invokeClose() {
      options.shortcuts.invoke(options.closeCommandId, { trigger: shell.closeButton });
    }

    shell.dialog.addEventListener("keydown", handleDialogKeydown);
    shell.element.addEventListener("pointerdown", handleScrimPointerdown);
    shell.closeButton.addEventListener("click", invokeClose);

    function dispose() {
      if (disposed) {
        return;
      }
      close({ restoreFocus: true });
      disposed = true;
      shell.dialog.removeEventListener("keydown", handleDialogKeydown);
      shell.element.removeEventListener("pointerdown", handleScrimPointerdown);
      shell.closeButton.removeEventListener("click", invokeClose);
      for (const [element, record] of connectedControls) {
        for (const [name, state] of Object.entries(record.attributes)) {
          restoreAttribute(element, name, state);
        }
      }
      connectedControls.clear();
      shell.element.remove();
    }

    const controller = Object.freeze({
      ...shell,
      close,
      control,
      dispose,
      isOpen: () => !shell.element.hidden,
      open,
    });
    return controller;
  }

  window.MetabrowserOverlay = Object.freeze({
    captureBackgroundState,
    createDialogShell,
    createModal,
    focusableElements,
    restoreBackgroundState,
  });
})();
