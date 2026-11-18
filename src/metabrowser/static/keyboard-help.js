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
  // and stay in Help. Seven is the most that keeps the strip within the panel's bottom
  // quarter with the navigation pane at its 180px minimum and the page at 100% zoom, the
  // rule the reveal check in docs/project/qa/qa-2026-09-19-v012-repository-library.md
  // measures it against. The
  // most the `reveal` surface lists at once is eight, on a file of a mirror's pin with a
  // hosted origin (Help, Quick Search, Files, Commits, Pulls, Up, Copy, Branch), so there
  // Branch drops. Each row of the revealed layer is 32px, a 20px keycap with 3px above
  // and below it and a 6px gap, so the layer is 32px a row plus 7: 13px of padding and
  // border, less the last gap. How many items a row holds depends on the face's label
  // widths, so the count cannot be read off the stylesheet. Headless Chrome 152, at the
  // 180px minimum: two items take two rows (71px), three or four take three (103px), five
  // to seven take four (135px), and eight take five (167px); at the default 300px, eight
  // take three (103px). A 1280 by 800 window gives the panel 629px at 100% zoom, so seven
  // cover 21% of it and eight 27%. At 200% zoom the panel has 229px and even two items
  // cover 31%, so no cap meets the rule there; the layer is a transient overlay, shown
  // only while Shift is held, so the cap targets 100% zoom. Safari's rows are not yet
  // measured.
  const REVEAL_STRIP_MAX_ITEMS = 7;
  // How far past its row the resting strip's items may reach and still all show. Layout
  // places boxes in a 64th of a pixel and the widths are read in that unit, so their sum
  // is exact; this only absorbs floating-point error in adding them, as
  // tests/dom/nav-toolbar-wrap.mjs does for the toolbars.
  const STRIP_FIT_EPSILON_PX = 0.001;
  /** @typedef {{ariaKeyshortcuts: string, preferred?: HelpBindingPresentation, range?: boolean, spoken: string, visible: readonly string[]}} HelpBindingPresentation */
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
   * several, as Control-N or Control-P, and at most `limit` items.
   * `lead` is an item the caller built and owns, which the layer keeps first and never
   * rebuilds or removes, as the resting strip keeps Shift ahead of every command.
   *
   * @param {HTMLElement} host
   * @param {readonly HelpGroupPresentation[]} snapshot
   * @param {(commandId: string, context: Record<string, unknown>) => boolean} invoke
   * @param {(container: HTMLElement, presentation: HelpBindingPresentation) => void} [append]
   * @param {{actions?: boolean, bindings?: "all" | "preferred", lead?: HTMLElement, limit?: number}} [stripOptions]
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
    const lead = stripOptions.lead ? [stripOptions.lead] : [];
    host.append(...lead, ...orderedElements);
    host.hidden = lead.length + orderedElements.length === 0;
  }

  /**
   * The resting strip's first item: Shift, which reveals every live key on the control it
   * reaches. It leads, ahead of `?`, because it is the one key that shows all the others
   * (the owner, 2026-11-18). It is no command, since no binding may use Shift
   * (docs/design-system.md, "Canonical Key Names"), so it is a reminder, a span like the
   * strip's other unactionable hints with its keycap from the single-key entry point, as
   * Help's closing note draws it. It is hidden from assistive technology, as the badges and
   * the revealed layer it calls up are: the reveal is paint only, and every key it shows
   * is announced at rest through `aria-keyshortcuts`. Built once, it costs a reconcile no
   * keycap.
   *
   * @param {Document} hostDocument
   * @param {(container: HTMLElement, key: string) => HTMLElement} appendKey
   */
  function buildRevealHint(hostDocument, appendKey) {
    const hint = hostDocument.createElement("span");
    hint.className = "nav-shortcut-hint";
    hint.setAttribute("aria-hidden", "true");
    const binding = hostDocument.createElement("span");
    binding.className = "nav-shortcut-binding";
    appendKey(binding, "Shift");
    const label = hostDocument.createElement("span");
    label.className = "nav-shortcut-label";
    label.textContent = "Reveal keys";
    hint.append(binding, label);
    return hint;
  }

  /**
   * How many of a one-row strip's items show, from its start: all of them when their
   * widths and the gaps between them fit `available`, and otherwise as many as fit, so the
   * last item drops first. The first item, the lead, always shows.
   *
   * @param {readonly number[]} widths
   * @param {number} available
   * @param {number} gap
   * @returns {number}
   */
  function stripItemsThatFit(widths, available, gap) {
    let shown = widths.length;
    let total = widths.reduce((sum, width) => sum + width, 0) + gap * Math.max(0, shown - 1);
    while (shown > 1 && total > available + STRIP_FIT_EPSILON_PX) {
      shown -= 1;
      total -= widths[shown] + gap;
    }
    return shown;
  }

  /** @param {string | undefined} value */
  function pixels(value) {
    return Number.parseFloat(value ?? "") || 0;
  }

  /**
   * Keep the resting strip to one row (the owner, 2026-11-18): where its items do not all
   * fit, it drops them from the end, Quick Search before Help, and never the lead, Shift.
   * A dropped item is `hidden`, so it leaves the tab order and the accessibility tree,
   * and its key stays in Help and on the revealed layer. The strip never wraps, so it is
   * always the one row the server reserves for it before the shell's tools load.
   *
   * `reconciled()` measures every item, shown, and fits again after a reconcile that
   * changed what the strip holds: an item added, removed, or replaced, or its text. A
   * reconcile that left it as it was, as most registrations and scope changes do, reads
   * no layout. A size change refits: the strip's own, as the pane is dragged, from the
   * widths measured last, and the lead's, as a face or the interface font set changes the
   * text, by measuring again. It refits in the observer's own callback, so no frame shows
   * an item cut off at the pane's edge. That changes no observed box: the strip's width is
   * the pane's and its height the lead's row, which a dropped or restored item, one keycap
   * tall, leaves as it is. Where nothing assistive technology reads shows, as where Shift,
   * hidden from it, shows alone, the strip's named group is hidden from it too, rather
   * than announced empty. Without a ResizeObserver, as in a browserless DOM, it returns
   * null and every item shows.
   *
   * @param {HTMLElement} host
   * @param {HTMLElement} lead
   * @returns {{dispose: () => void, reconciled: () => void} | null}
   */
  function keepStripOnOneRow(host, lead) {
    const found = host.ownerDocument?.defaultView;
    if (!found || typeof found.ResizeObserver !== "function") {
      return null;
    }
    const view = found;
    /** @type {Map<Element, number>} */
    let widths = new Map();
    /** What the strip held when it was last fitted after a reconcile, and their text.
     * @type {readonly HTMLElement[]} */
    let held = [];
    /** @type {readonly string[]} */
    let heldText = [];
    const stripItems = () =>
      /** @type {HTMLElement[]} */ (
        Array.from(host.children).filter(
          (child) => !child.classList.contains("nav-shortcut-reveal"),
        )
      );
    /** @param {boolean} remeasure */
    function fit(remeasure) {
      const items = stripItems();
      if (remeasure || items.some((item) => !widths.has(item))) {
        for (const item of items) {
          item.hidden = false;
        }
        widths = new Map(items.map((item) => [item, item.getBoundingClientRect().width]));
      }
      const style = view.getComputedStyle(host);
      const available =
        host.getBoundingClientRect().width -
        pixels(style.paddingLeft) -
        pixels(style.paddingRight) -
        pixels(style.borderLeftWidth) -
        pixels(style.borderRightWidth);
      // A strip with no box, in a pane that is not laid out, shows everything until it has.
      const shown =
        available > 0
          ? stripItemsThatFit(
              items.map((item) => widths.get(item) ?? 0),
              available,
              pixels(style.columnGap),
            )
          : items.length;
      items.forEach((item, index) => {
        if (item.hidden !== index >= shown) {
          item.hidden = index >= shown;
        }
      });
      const readable = items.some(
        (item, index) => index < shown && item.getAttribute("aria-hidden") !== "true",
      );
      if (readable) {
        host.removeAttribute("aria-hidden");
      } else if (host.getAttribute("aria-hidden") !== "true") {
        host.setAttribute("aria-hidden", "true");
      }
    }
    function reconciled() {
      const items = stripItems();
      const text = items.map((item) => item.textContent ?? "");
      if (
        items.length === held.length &&
        items.every((item, index) => item === held[index] && text[index] === heldText[index])
      ) {
        return;
      }
      held = items;
      heldText = text;
      fit(true);
    }
    const sizes = new view.ResizeObserver((entries) => {
      fit(entries.some((entry) => entry.target === lead));
    });
    sizes.observe(host);
    sizes.observe(lead);
    return Object.freeze({
      dispose: () => {
        sizes.disconnect();
        host.removeAttribute("aria-hidden");
      },
      reconciled,
    });
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

    const revealHint = buildRevealHint(hostDocument, options.shortcuts.appendKey);
    const stripFit = keepStripOnOneRow(options.hintHost, revealHint);

    function renderHints() {
      reconcileHintStrip(
        options.hintHost,
        options.shortcuts.snapshot("nav"),
        options.shortcuts.invoke,
        options.shortcuts.appendBinding,
        { lead: revealHint },
      );
      stripFit?.reconciled();
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
      stripFit?.dispose();
      clearHintStrip(options.hintHost);
      revealHint.remove();
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
    stripItemsThatFit,
  });
})();
