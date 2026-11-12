// Registry-rendered Help dialog and contextual navigation shortcut chrome.

(() => {
  const PROJECT_URL = "https://github.com/jlevy/metabrowser";
  // The registry events that change what the strip shows: the `nav` surface
  // gains or loses a command on a registration, and a contextual command
  // appears or goes with its scope.
  const HINT_EVENT_KINDS = new Set(["registration", "scope"]);
  // The events that change only the revealed strip: the reveal starting or ending, a
  // target attached, moved, or released, and the liveness read again after a key.
  // At rest no strip shows them, so they cost nothing then.
  const REVEAL_EVENT_KINDS = new Set(["dispatch", "reveal", "target"]);
  // The most items the revealed strip lists; later ones in the surface order drop first
  // and stay in Help. PROVISIONAL: measured in Chrome, not yet chosen. The most the
  // `reveal` surface lists at once is eight, on a file of a mirror's pin with a hosted
  // origin (Help, Quick Search, Files, Commits, Pulls, Up, Copy, Branch). Each row of the
  // revealed layer is 32px, a 20px keycap with 3px above and below it and a 6px gap, so
  // the layer is 32px a row plus 7: 13px of padding and border, less the last gap. How
  // many items a row holds depends on the face's label widths, so the count cannot be
  // read off the stylesheet. Headless Chrome 152, at the navigation pane's 180px minimum:
  // two items take two rows (71px), three or four take three (103px), five to seven take
  // four (135px), and eight take five (167px); at the default 300px, eight take three
  // (103px). A 1280 by 800 window gives the panel 629px at 100% zoom, so seven cover 21%
  // of it and eight 27%; at 200% zoom it has 229px, and even two cover 31%. So no cap
  // keeps the strip within the panel's bottom quarter at 200% zoom, and the reveal check
  // in docs/qa-v012-repository-library.md leaves the choice open. What remains: the same
  // widths in Safari, and a decision on the rule the cap serves.
  const REVEAL_STRIP_MAX_ITEMS = 8;
  /** @typedef {{ariaKeyshortcuts: string, preferred?: HelpBindingPresentation, spoken: string, visible: readonly string[]}} HelpBindingPresentation */
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
   * @property {readonly {key: string}[]} bindings
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
   * Reconcile one strip layer with a snapshot. The resting strip names one way into each
   * command and makes the controls it owns buttons; the revealed layer, `actions: false`
   * with `bindings: "all"`, is a reminder only, every binding of an item that coalesces
   * several, as `N` or `P`, and at most `limit` items.
   *
   * @param {HTMLElement} host
   * @param {readonly HelpGroupPresentation[]} snapshot
   * @param {(commandId: string, context: Record<string, unknown>) => boolean} invoke
   * @param {(container: HTMLElement, presentation: HelpBindingPresentation) => void} [append]
   * @param {{actions?: boolean, bindings?: "all" | "preferred", limit?: number}} [stripOptions]
   */
  function reconcileHintStrip(host, snapshot, invoke, append, stripOptions = {}) {
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
    const presentations = snapshot
      .flatMap((group) => group.commands)
      .slice(0, stripOptions.limit ?? Number.POSITIVE_INFINITY);
    const nextKeys = new Set();
    /** @type {HTMLElement[]} */
    const orderedElements = [];
    for (const presentation of presentations) {
      const actionable = stripOptions.actions !== false && Boolean(presentation.control);
      const key = actionable ? presentation.id : `hint:${presentation.commandIds.join("+")}`;
      nextKeys.add(key);
      let record = records.get(key);
      if (!record) {
        const element = hostDocument.createElement(actionable ? "button" : "span");
        // Deliberately not `.btn`: the keycap inside is the affordance, and a
        // button chrome here would box the key and its label a second time.
        element.className = actionable ? "nav-shortcut-action" : "nav-shortcut-hint";
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
      // The strip is a reminder, not the reference. It names one way in; Help
      // carries the aliases. aria-keyshortcuts below still advertises all of
      // them, because every alias really does work.
      appendBinding(
        binding,
        stripOptions.bindings === "all"
          ? presentation.bindings
          : presentation.bindings.preferred || presentation.bindings,
      );
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

  /**
   * @param {Document} hostDocument
   * @param {HTMLElement} modalBody
   * @param {(container: HTMLElement, key: string) => HTMLElement} appendKey
   */
  function buildHelpContent(hostDocument, modalBody, appendKey) {
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
    // Guidance for after Help closes: inside its exclusive scope, a held Shift shows
    // only Help's own keys. The key in the sentence is a keycap, as every key in prose is.
    const note = hostDocument.createElement("p");
    note.className = "help-shortcut-note";
    note.append("Press ");
    appendKey(note, "Shift");
    note.append(" to see relevant shortcut reminders.");
    shortcutsSection.append(shortcutsHeading, groups, note);
    modalBody.append(description, project, shortcutsSection);
    return { groups, projectLink };
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
      bindings: [{ key: "?" }, { key: "Escape" }],
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
    const { groups: groupsHost, projectLink } = buildHelpContent(
      hostDocument,
      modal.body,
      options.shortcuts.appendKey,
    );
    let disposed = false;
    // Help's groups are rendered when it opens and, while it is open, on a
    // registration. A registration while it is closed only marks them stale, so
    // a navigation that registers and releases commands rebuilds nothing.
    let helpStale = true;
    /** @type {Promise<void> | null} */
    let decoration = null;
    /** Opening Help does not require a file view or make its helper an eager asset.
     * @param {HTMLElement | null} [trigger]
     */
    function open(trigger = null) {
      if (helpStale) {
        renderHelp();
      }
      modal?.open(trigger);
      if (decoration === null && !disposed) {
        decoration = window.metabrowser
          .ensureAsset("sdk-views")
          .then(() => {
            if (!disposed) {
              window.metabrowser.decorateExternalLink(projectLink);
            }
          })
          .catch(() => {
            decoration = null;
          });
      }
    }
    const unregisterOpen = options.shortcuts.register({
      bindings: [{ key: "?" }],
      control: modal.control,
      copy: {
        action: "Help",
        description: "Open Help for a description of Metabrowser and all keyboard shortcuts.",
        hint: "Help",
      },
      group: "anywhere",
      handler: (context) => {
        const trigger = context.trigger;
        open(trigger && typeof trigger === "object" ? /** @type {HTMLElement} */ (trigger) : null);
        return true;
      },
      id: "help.open",
      order: 10,
      scope: "global",
      surfaces: { help: "always", nav: "always", reveal: "always" },
    });

    function renderHelp() {
      helpStale = false;
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
      renderRevealLayer();
    }

    /** @type {HTMLElement | null} */
    let revealLayer = null;

    /**
     * While Shift reveals the keys, a second layer of the strip lists the `reveal`
     * surface: the common keys that are live now. It is a reminder, hidden from
     * assistive technology like the badges, and the resting strip under it keeps its
     * content and height, so the panel above neither reflows nor scrolls. The layer
     * exists only while revealed.
     */
    function renderRevealLayer() {
      if (!options.shortcuts.isRevealed()) {
        if (revealLayer) {
          clearHintStrip(revealLayer);
          revealLayer.remove();
          revealLayer = null;
        }
        return;
      }
      if (!revealLayer) {
        revealLayer = hostDocument.createElement("div");
        revealLayer.className = "nav-shortcut-reveal";
        revealLayer.setAttribute("aria-hidden", "true");
        revealLayer.setAttribute("data-surface", "reveal");
        options.hintHost.append(revealLayer);
      }
      reconcileHintStrip(
        revealLayer,
        options.shortcuts.snapshot("reveal", { live: true }),
        options.shortcuts.invoke,
        options.shortcuts.appendBinding,
        { actions: false, bindings: "all", limit: REVEAL_STRIP_MAX_ITEMS },
      );
    }

    renderHints();
    const unsubscribe = options.shortcuts.subscribe((event) => {
      const kinds = event.kind === "batch" ? event.kinds || [] : [event.kind];
      if (kinds.includes("registration")) {
        if (modal?.isOpen()) {
          renderHelp();
        } else {
          helpStale = true;
        }
      }
      if (kinds.some((kind) => HINT_EVENT_KINDS.has(kind))) {
        renderHints();
      } else if (
        kinds.some((kind) => REVEAL_EVENT_KINDS.has(kind)) &&
        (revealLayer !== null || options.shortcuts.isRevealed())
      ) {
        renderRevealLayer();
      }
    });

    function dispose() {
      disposed = true;
      unsubscribe();
      if (revealLayer) {
        clearHintStrip(revealLayer);
        revealLayer.remove();
        revealLayer = null;
      }
      clearHintStrip(options.hintHost);
      unregisterOpen();
      modal?.dispose();
      modal = null;
      unregisterClose();
    }

    return Object.freeze({
      close: () => modal?.close(),
      dispose,
      open,
    });
  }

  window.MetabrowserKeyboardHelp = Object.freeze({
    create,
    reconcileHintStrip,
    renderHelpGroups,
  });
})();
