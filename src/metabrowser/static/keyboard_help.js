// Registry-rendered Help dialog and contextual navigation shortcut chrome.

(() => {
  const PROJECT_URL = "https://github.com/jlevy/metabrowser";
  /** @typedef {{ariaKeyshortcuts: string, spoken: string, visible: readonly {keys: readonly string[], separators: readonly string[]}[]}} HelpBindingPresentation */
  /** @typedef {{connect: (element: HTMLElement) => () => void}} HelpControlBinding */
  /**
   * @typedef {object} HelpCommandPresentation
   * @property {HelpBindingPresentation} bindings
   * @property {readonly string[]} commandIds
   * @property {HelpControlBinding} [control]
   * @property {{action: string, description: string, hint: string}} copy
   * @property {string} group
   * @property {string} id
   * @property {string} scope
   */
  /** @typedef {{commands: readonly HelpCommandPresentation[], context: string, id: string, label: string}} HelpGroupPresentation */
  /**
   * @typedef {object} HelpCommand
   * @property {boolean} [allowInEditable]
   * @property {readonly {key: string, modifiers?: Record<string, string>}[]} bindings
   * @property {HelpControlBinding} [control]
   * @property {{action: string, description: string, hint: string}} copy
   * @property {string} group
   * @property {(context: Record<string, unknown>) => boolean} handler
   * @property {string} id
   * @property {number} order
   * @property {string} scope
   * @property {Record<string, "active" | "always">} surfaces
   */
  /**
   * @typedef {object} HelpModalController
   * @property {HTMLElement} body
   * @property {(options?: {restoreFocus?: boolean}) => void} close
   * @property {HelpControlBinding} control
   * @property {() => void} dispose
   * @property {() => boolean} isOpen
   * @property {(trigger?: HTMLElement | null) => void} open
   */
  /** @type {WeakMap<HTMLElement, Map<string, HintRecord>>} */
  const hintStates = new WeakMap();

  /**
   * @typedef {object} HintRecord
   * @property {(() => void) | null} disconnectControl
   * @property {HTMLElement} element
   * @property {((event: Event) => void) | null} listener
   * @property {HelpCommandPresentation} presentation
   */
  /**
   * @typedef {object} ShortcutRegistry
   * @property {(container: HTMLElement, presentation: HelpBindingPresentation) => void} appendBinding
   * @property {(scope: string, options?: {exclusive?: boolean}) => () => void} activateScope
   * @property {(commandId: string, context?: Record<string, unknown>) => boolean} invoke
   * @property {(commandId: string) => HelpCommandPresentation | null} present
   * @property {(command: HelpCommand) => () => void} register
   * @property {(surface: string, options?: {includeInactive?: boolean}) => readonly HelpGroupPresentation[]} snapshot
   * @property {(listener: (event: {kind: string}) => void) => () => void} subscribe
   */

  /**
   * @param {HTMLElement} body
   * @param {readonly HelpGroupPresentation[]} snapshot
   * @param {(container: HTMLElement, presentation: HelpBindingPresentation) => void} [append]
   */
  function renderHelpGroups(body, snapshot, append) {
    const hostDocument = body.ownerDocument;
    const appendBinding =
      append ||
      ((container, presentation) =>
        window.MetabrowserKeyboardShortcuts.appendBinding(hostDocument, container, presentation));
    const sections = snapshot.map((group) => {
      const section = hostDocument.createElement("section");
      section.className = "help-shortcut-group";
      const heading = hostDocument.createElement("h4");
      heading.className = "help-shortcut-heading";
      heading.textContent = group.label;
      const context = hostDocument.createElement("p");
      context.className = "help-shortcut-context";
      context.textContent = group.context;
      const commands = hostDocument.createElement("div");
      commands.className = "help-command-list";
      for (const command of group.commands) {
        const row = hostDocument.createElement("div");
        row.className = "help-command-row";
        const binding = hostDocument.createElement("span");
        binding.className = "help-command-binding";
        appendBinding(binding, command.bindings);
        const copy = hostDocument.createElement("span");
        copy.className = "help-command-copy";
        const label = hostDocument.createElement("strong");
        label.className = "help-command-label";
        label.textContent = command.copy.action;
        const description = hostDocument.createElement("span");
        description.className = "help-command-description";
        description.textContent = command.copy.description;
        copy.append(label, description);
        row.append(binding, copy);
        commands.append(row);
      }
      section.append(heading, context, commands);
      return section;
    });
    body.replaceChildren(...sections);
  }

  /** @param {HTMLElement} host */
  function clearHintStrip(host) {
    const records = hintStates.get(host);
    if (records) {
      for (const record of records.values()) {
        record.disconnectControl?.();
        if (record.listener) {
          record.element.removeEventListener("click", record.listener);
        }
        record.element.remove();
      }
    }
    hintStates.delete(host);
    host.hidden = true;
  }

  /**
   * @param {HTMLElement} host
   * @param {readonly HelpGroupPresentation[]} snapshot
   * @param {(commandId: string, context: Record<string, unknown>) => boolean} invoke
   * @param {(container: HTMLElement, presentation: HelpBindingPresentation) => void} [append]
   */
  function reconcileHintStrip(host, snapshot, invoke, append) {
    const hostDocument = host.ownerDocument;
    const appendBinding =
      append ||
      ((container, presentation) =>
        window.MetabrowserKeyboardShortcuts.appendBinding(hostDocument, container, presentation));
    let records = hintStates.get(host);
    if (!records) {
      records = new Map();
      hintStates.set(host, records);
    }
    const presentations = snapshot.flatMap((group) => group.commands);
    const nextKeys = new Set();
    /** @type {HTMLElement[]} */
    const orderedElements = [];
    for (const presentation of presentations) {
      const actionable = Boolean(presentation.control);
      const key = actionable ? presentation.id : `hint:${presentation.commandIds.join("+")}`;
      nextKeys.add(key);
      let record = records.get(key);
      if (!record) {
        const element = hostDocument.createElement(actionable ? "button" : "span");
        element.className = actionable ? "btn nav-shortcut-action" : "nav-shortcut-hint";
        if (actionable) {
          element.setAttribute("type", "button");
          const listener = () => invoke(presentation.id, { trigger: element });
          element.addEventListener("click", listener);
          record = {
            disconnectControl: presentation.control?.connect(element) || null,
            element,
            listener,
            presentation,
          };
        } else {
          record = { disconnectControl: null, element, listener: null, presentation };
        }
        records.set(key, record);
      } else if (record.presentation.control !== presentation.control) {
        record.disconnectControl?.();
        record.disconnectControl = presentation.control?.connect(record.element) || null;
      }
      if (record.presentation !== presentation) {
        record.presentation = presentation;
      }
      const binding = hostDocument.createElement("span");
      binding.className = "nav-shortcut-binding";
      appendBinding(binding, presentation.bindings);
      const label = hostDocument.createElement("span");
      label.className = "nav-shortcut-label";
      label.textContent = presentation.copy.hint;
      record.element.replaceChildren(binding, label);
      if (actionable) {
        record.element.setAttribute("aria-label", presentation.copy.action);
        if (presentation.bindings.ariaKeyshortcuts) {
          record.element.setAttribute("aria-keyshortcuts", presentation.bindings.ariaKeyshortcuts);
        } else {
          record.element.removeAttribute("aria-keyshortcuts");
        }
      }
      orderedElements.push(record.element);
    }
    for (const [key, record] of records) {
      if (nextKeys.has(key)) {
        continue;
      }
      record.disconnectControl?.();
      if (record.listener) {
        record.element.removeEventListener("click", record.listener);
      }
      record.element.remove();
      records.delete(key);
    }
    host.append(...orderedElements);
    host.hidden = orderedElements.length === 0;
  }

  /** @param {Document} hostDocument @param {HTMLElement} modalBody */
  function buildHelpContent(hostDocument, modalBody) {
    const description = hostDocument.createElement("section");
    description.className = "help-description";
    for (const sentence of [
      "Metabrowser runs a local server for one folder.",
      "Use the navigation pane and filters to explore its live file inventory; select a file to open a preview in the main pane.",
      "Built-in and trusted installed plugins provide views for different file types.",
    ]) {
      const paragraph = hostDocument.createElement("p");
      paragraph.textContent = sentence;
      description.append(paragraph);
    }

    const project = hostDocument.createElement("section");
    project.className = "help-project";
    const projectLink = hostDocument.createElement("a");
    projectLink.href = PROJECT_URL;
    projectLink.setAttribute("href", PROJECT_URL);
    projectLink.setAttribute("target", "_blank");
    projectLink.setAttribute("rel", "noopener noreferrer");
    projectLink.setAttribute("aria-label", "Metabrowser on GitHub (opens in a new tab)");
    projectLink.textContent = "Metabrowser on GitHub";
    project.append(projectLink);

    const shortcutsSection = hostDocument.createElement("section");
    shortcutsSection.className = "help-shortcuts";
    const shortcutsHeading = hostDocument.createElement("h3");
    shortcutsHeading.className = "help-section-heading";
    shortcutsHeading.textContent = "Keyboard shortcuts";
    const groups = hostDocument.createElement("div");
    groups.className = "help-shortcut-groups";
    shortcutsSection.append(shortcutsHeading, groups);
    modalBody.append(description, project, shortcutsSection);
    return groups;
  }

  /**
   * @param {{
   *   document?: Document,
   *   hintHost: HTMLElement,
   *   overlay: Window["MetabrowserOverlay"],
   *   resolveFocusFallback?: (previous: HTMLElement | null) => HTMLElement | null,
   *   shortcuts: ReturnType<Window["MetabrowserKeyboardShortcuts"]["create"]>,
   * }} options
   */
  function create(options) {
    if (!options?.shortcuts || !options.overlay || !options.hintHost) {
      throw new TypeError("Keyboard Help requires shortcuts, overlays, and a hint host");
    }
    const hostDocument = options.document || window.document;
    /** @type {HelpModalController | null} */
    let modal = null;
    const unregisterClose = options.shortcuts.register({
      allowInEditable: true,
      bindings: [{ key: "?", modifiers: { shift: "allow" } }, { key: "Escape" }],
      copy: {
        action: "Close Help",
        description: "Close Help and restore focus to the previous control.",
        hint: "Close",
      },
      group: "help",
      handler: () => {
        if (!modal?.isOpen()) {
          return false;
        }
        modal.close();
        return true;
      },
      id: "help.close",
      order: 10,
      scope: "help",
      surfaces: { help: "always" },
    });
    modal = options.overlay.createModal({
      className: "help-dialog",
      closeCommandId: "help.close",
      document: hostDocument,
      resolveFocusFallback: options.resolveFocusFallback,
      scope: "help",
      shortcuts: options.shortcuts,
      title: "Help",
    });
    const groupsHost = buildHelpContent(hostDocument, modal.body);
    const unregisterOpen = options.shortcuts.register({
      bindings: [{ key: "?", modifiers: { shift: "allow" } }],
      control: modal.control,
      copy: {
        action: "Help",
        description: "Open Help for a description of Metabrowser and all keyboard shortcuts.",
        hint: "Help",
      },
      group: "anywhere",
      handler: (context) => {
        const trigger = context.trigger;
        modal?.open(
          trigger && typeof trigger === "object" ? /** @type {HTMLElement} */ (trigger) : null,
        );
        return true;
      },
      id: "help.open",
      order: 10,
      scope: "global",
      surfaces: { help: "always", nav: "always" },
    });

    function renderHelp() {
      renderHelpGroups(
        groupsHost,
        options.shortcuts.snapshot("help", { includeInactive: true }),
        options.shortcuts.appendBinding,
      );
    }

    function renderHints() {
      reconcileHintStrip(
        options.hintHost,
        options.shortcuts.snapshot("nav"),
        options.shortcuts.invoke,
        options.shortcuts.appendBinding,
      );
    }

    renderHelp();
    renderHints();
    const unsubscribe = options.shortcuts.subscribe((event) => {
      if (event.kind === "registration") {
        renderHelp();
      }
      renderHints();
    });

    function dispose() {
      unsubscribe();
      clearHintStrip(options.hintHost);
      unregisterOpen();
      modal?.dispose();
      modal = null;
      unregisterClose();
    }

    return Object.freeze({
      close: () => modal?.close(),
      dispose,
      open: (trigger = null) => modal?.open(trigger),
    });
  }

  window.MetabrowserKeyboardHelp = Object.freeze({
    create,
    reconcileHintStrip,
    renderHelpGroups,
  });
})();
