// Shared command dispatch and presentation for application keyboard shortcuts.

(() => {
  /**
   * One key, and nothing else: no shortcut uses a modifier, so a binding
   * states no modifier policy (docs/design-system.md, "Binding Grammar and
   * Accessibility").
   *
   * @typedef {object} ShortcutBinding
   * @property {string} key
   */
  /** @typedef {"digit" | "letter" | "named" | "punctuation"} KeyClass */
  /** @typedef {Readonly<{kind: string, commandId?: string, kinds?: readonly string[], scope?: string}>} ShortcutEvent */
  /**
   * @typedef {object} BindingPresentation
   * @property {string} ariaKeyshortcuts
   * @property {BindingPresentation} [preferred]
   * @property {string} spoken
   * @property {readonly Readonly<{keys: readonly string[], separators: readonly string[]}>[]} visible
   */
  /** @typedef {{connect: (element: HTMLElement) => () => void}} ShortcutControlBinding */
  /**
   * @typedef {object} ShortcutCommand
   * @property {boolean} [allowInEditable]
   * @property {readonly ShortcutBinding[]} bindings
   * @property {ShortcutControlBinding} [control]
   * @property {{action: string, description: string, hint: string}} copy
   * @property {string} group
   * @property {(context: Record<string, unknown>) => boolean} handler
   * @property {string} id
   * @property {number} order
   * @property {boolean} [repeat]
   * @property {string} scope
   * @property {Readonly<Record<string, "active" | "always">>} surfaces
   * @property {(context: Record<string, unknown>) => boolean} [available]
   */
  /**
   * @typedef {object} ShortcutPresentation
   * @property {BindingPresentation} bindings
   * @property {Readonly<ShortcutControlBinding> | undefined} control
   * @property {Readonly<{action: string, description: string, hint: string}>} copy
   * @property {string} group
   * @property {string} id
   * @property {readonly string[]} commandIds
   * @property {string} scope
   * @property {Readonly<Record<string, "active" | "always">>} surfaces
   */
  /**
   * @typedef {object} ShortcutEntry
   * @property {ShortcutCommand} descriptor
   * @property {number} order
   * @property {Readonly<ShortcutPresentation>} presentation
   */

  // A key event with any of these held never matches a shortcut: the chords
  // belong to the browser and the platform. Shift is ignored instead, so
  // holding it never changes what a key means. AltGr reports Ctrl and Alt, so
  // punctuation typed with it stays outside the shortcuts too.
  /** @type {readonly ("altKey" | "ctrlKey" | "metaKey")[]} */
  const DISQUALIFYING_MODIFIERS = Object.freeze(["altKey", "ctrlKey", "metaKey"]);
  // Scopes that are always active below the activated ones, in order.
  const PERMANENT_SCOPES = Object.freeze(["global", "view-tabs"]);

  /** @type {Readonly<Record<string, Readonly<{aria: string, spoken: string, visible: string}>>>} */
  const KEY_DEFINITIONS = Object.freeze({
    " ": Object.freeze({ aria: "Space", spoken: "Space", visible: "Space" }),
    "/": Object.freeze({ aria: "", spoken: "slash", visible: "/" }),
    "?": Object.freeze({ aria: "", spoken: "Question mark", visible: "?" }),
    ArrowDown: Object.freeze({ aria: "ArrowDown", spoken: "Down arrow", visible: "↓" }),
    ArrowLeft: Object.freeze({ aria: "ArrowLeft", spoken: "Left arrow", visible: "←" }),
    ArrowRight: Object.freeze({ aria: "ArrowRight", spoken: "Right arrow", visible: "→" }),
    ArrowUp: Object.freeze({ aria: "ArrowUp", spoken: "Up arrow", visible: "↑" }),
    Delete: Object.freeze({ aria: "Delete", spoken: "Delete", visible: "Delete" }),
    End: Object.freeze({ aria: "End", spoken: "End", visible: "End" }),
    Enter: Object.freeze({ aria: "Enter", spoken: "Enter", visible: "Enter" }),
    Escape: Object.freeze({ aria: "Escape", spoken: "Escape", visible: "Esc" }),
    F2: Object.freeze({ aria: "F2", spoken: "F2", visible: "F2" }),
    Home: Object.freeze({ aria: "Home", spoken: "Home", visible: "Home" }),
  });

  // Keys that Shift turns into text selection inside a field: a command never
  // takes Shift+Arrow, Shift+Home, or Shift+End from a text field, even one
  // that opted in with allowInEditable.
  const TEXT_SELECTION_KEYS = new Set([
    "ArrowDown",
    "ArrowLeft",
    "ArrowRight",
    "ArrowUp",
    "End",
    "Home",
  ]);

  /** @type {Readonly<Record<string, Readonly<{context: string, label: string, order: number}>>>} */
  const GROUP_DEFINITIONS = Object.freeze({
    anywhere: Object.freeze({
      context: "Available outside text fields.",
      label: "Anywhere",
      order: 10,
    }),
    "main-tabs": Object.freeze({
      context: "Available outside text fields.",
      label: "Main tabs",
      order: 15,
    }),
    navigation: Object.freeze({
      context: "Available while a file-tree row has focus.",
      label: "Navigation",
      order: 20,
    }),
    "pull-requests": Object.freeze({
      context: "Available while a pull-request row has focus.",
      label: "Pull requests",
      order: 25,
    }),
    "pull-stack": Object.freeze({
      context: "Available while a pull request in a stack is open.",
      label: "Pull request stack",
      order: 27,
    }),
    "quick-file": Object.freeze({
      context: "Available while Quick Search is open.",
      label: "Quick Search",
      order: 30,
    }),
    help: Object.freeze({
      context: "Available while Help is open.",
      label: "Help",
      order: 40,
    }),
  });

  // Keys that are named but never bound: the single-key entry point renders
  // them, as the Shift in Help's closing note, and the binding validator
  // refuses them.
  /** @type {Readonly<Record<string, Readonly<{aria: string, spoken: string, visible: string}>>>} */
  const STANDALONE_KEY_DEFINITIONS = Object.freeze({
    Shift: Object.freeze({ aria: "Shift", spoken: "Shift", visible: "Shift" }),
  });

  /** @param {string} key */
  function keyDefinition(key) {
    const known = KEY_DEFINITIONS[key];
    if (known) {
      return known;
    }
    if (/^[a-z0-9]$/i.test(key)) {
      const label = key.toUpperCase();
      return Object.freeze({ aria: label, spoken: label, visible: label });
    }
    throw new TypeError(`Unsupported shortcut key: ${key}`);
  }

  /**
   * How a normalized binding key matches an event: a letter in either case, a
   * digit by the character and then by its digit-row key, punctuation by the
   * character typed, and a named key by its name.
   *
   * @param {string} key
   * @returns {KeyClass}
   */
  function keyClass(key) {
    if (/^[a-z]$/.test(key)) {
      return "letter";
    }
    if (isDigitKey(key)) {
      return "digit";
    }
    return key === "?" || key === "/" ? "punctuation" : "named";
  }

  /** @param {ShortcutBinding} binding @returns {Readonly<ShortcutBinding>} */
  function normalizeBinding(binding) {
    if (!binding || typeof binding.key !== "string") {
      throw new TypeError("Shortcut bindings require a key");
    }
    if (/** @type {{modifiers?: unknown}} */ (binding).modifiers !== undefined) {
      // A policy here would let one command at a time reintroduce a chord, or a
      // key whose meaning Shift changes.
      throw new TypeError(`Shortcut bindings state no modifier policy: ${binding.key}`);
    }
    // Rejects any key the vocabulary cannot name; the definition itself is
    // resolved again at presentation time.
    keyDefinition(binding.key);
    const key = /^[a-z]$/i.test(binding.key) ? binding.key.toLowerCase() : binding.key;
    return Object.freeze({ key });
  }

  /** @param {ShortcutBinding} binding */
  function bindingSignature(binding) {
    return normalizeBinding(binding).key;
  }

  /** @param {string} key */
  function isDigitKey(key) {
    return /^[0-9]$/.test(key);
  }

  /**
   * Whether an event is this binding's key. Shift is ignored for every key
   * class, except that inside a text field Shift with a selection key (an
   * arrow, Home, or End) belongs to the field, where it extends the text
   * selection. Shift+Enter and Shift+Escape still act. Ctrl, Alt, and Meta
   * always disqualify the event.
   *
   * The physical pass matches a digit binding by its digit-row key, for an
   * event whose character is not a digit: US Shift+1 types `!`, and AZERTY's
   * unshifted digit row types `&é"'(`. The dispatcher takes it only after the
   * character matched nothing, so German Shift+7, which types `/`, stays `/`.
   * Numpad digits match by character.
   *
   * @param {KeyboardEvent} event
   * @param {ShortcutBinding} binding
   * @param {{physical?: boolean}} [matchOptions]
   */
  function eventMatchesBinding(event, binding, matchOptions = {}) {
    const normalized = normalizeBinding(binding);
    if (DISQUALIFYING_MODIFIERS.some((field) => event[field])) {
      return false;
    }
    const bindingClass = keyClass(normalized.key);
    if (matchOptions.physical) {
      return (
        bindingClass === "digit" &&
        // Digit1 through Digit9, the keys the navigation pane's tab digits use.
        /^[1-9]$/.test(normalized.key) &&
        !isDigitKey(event.key) &&
        event.code === `Digit${normalized.key}`
      );
    }
    const eventKey = /^[a-z]$/i.test(event.key) ? event.key.toLowerCase() : event.key;
    if (eventKey !== normalized.key) {
      return false;
    }
    return !(
      bindingClass === "named" &&
      event.shiftKey &&
      TEXT_SELECTION_KEYS.has(normalized.key) &&
      isEditableTarget(event.target)
    );
  }

  /** @param {EventTarget | null} target */
  function isEditableTarget(target) {
    if (!target || typeof (/** @type {{tagName?: unknown}} */ (target).tagName) !== "string") {
      return false;
    }
    const element = /** @type {HTMLElement} */ (target);
    const tagName = element.tagName.toLowerCase();
    return (
      tagName === "input" ||
      tagName === "textarea" ||
      tagName === "select" ||
      element.isContentEditable
    );
  }

  /** @param {readonly ShortcutBinding[]} bindings @returns {BindingPresentation} */
  function describeBindings(bindings) {
    if (!Array.isArray(bindings) || bindings.length === 0) {
      throw new TypeError("Presented commands require at least one binding");
    }
    const alternatives = bindings.map((binding) => {
      const definition = keyDefinition(normalizeBinding(binding).key);
      return Object.freeze({
        aria: definition.aria,
        spoken: definition.spoken,
        visible: Object.freeze({
          keys: Object.freeze([definition.visible]),
          separators: Object.freeze([]),
        }),
      });
    });
    const preferred = alternatives[0];
    return Object.freeze({
      ariaKeyshortcuts: alternatives
        .map((alternative) => alternative.aria)
        .filter(Boolean)
        .join(" "),
      // The first binding is the one a surface shows when it has room for a
      // single key. Aliases stay bound and stay listed in Help; a compact
      // surface just names one way in rather than spelling out every way.
      preferred: Object.freeze({
        ariaKeyshortcuts: preferred.aria,
        spoken: preferred.spoken,
        visible: Object.freeze([preferred.visible]),
      }),
      spoken: alternatives.map((alternative) => alternative.spoken).join(" or "),
      visible: Object.freeze(alternatives.map((alternative) => alternative.visible)),
    });
  }

  /**
   * @param {Document} hostDocument
   * @param {HTMLElement} container
   * @param {BindingPresentation} presentation
   */
  function appendBinding(hostDocument, container, presentation) {
    const complex =
      presentation.visible.length > 1 ||
      presentation.visible.some((alternative) => alternative.keys.length > 1);
    if (complex) {
      const spoken = hostDocument.createElement("span");
      spoken.className = "visually-hidden";
      spoken.textContent = presentation.spoken;
      container.append(spoken);
    }
    presentation.visible.forEach((alternative, alternativeIndex) => {
      if (alternativeIndex > 0) {
        const separator = hostDocument.createElement("span");
        separator.className = "shortcut-binding-separator";
        separator.textContent = "or";
        if (complex) {
          separator.setAttribute("aria-hidden", "true");
        }
        container.append(separator);
      }
      alternative.keys.forEach((key, keyIndex) => {
        if (keyIndex > 0) {
          const separator = hostDocument.createElement("span");
          separator.className = "shortcut-binding-separator";
          separator.textContent = alternative.separators[keyIndex - 1] || "+";
          if (complex) {
            separator.setAttribute("aria-hidden", "true");
          }
          container.append(separator);
        }
        const keycap = createKeycap(hostDocument, key);
        if (complex) {
          keycap.setAttribute("aria-hidden", "true");
        }
        container.append(keycap);
      });
    });
  }

  /** @param {Document} hostDocument @param {string} label */
  function createKeycap(hostDocument, label) {
    const keycap = hostDocument.createElement("kbd");
    keycap.className = "kbd";
    keycap.textContent = label;
    return keycap;
  }

  /**
   * One key that is not a binding: a binding key, or a standalone name such
   * as `Shift`, which reads as its name.
   *
   * @param {string} key
   */
  function describeKey(key) {
    if (typeof key !== "string") {
      throw new TypeError("A described key must be a string");
    }
    return Object.hasOwn(STANDALONE_KEY_DEFINITIONS, key)
      ? STANDALONE_KEY_DEFINITIONS[key]
      : keyDefinition(normalizeBinding({ key }).key);
  }

  /**
   * Render one key as one keycap and return it, so a caller can mark it, as a
   * badge marks its keycap hidden from assistive technology.
   *
   * @param {Document} hostDocument
   * @param {HTMLElement} container
   * @param {string} key
   */
  function appendKey(hostDocument, container, key) {
    const keycap = createKeycap(hostDocument, describeKey(key).visible);
    container.append(keycap);
    return keycap;
  }

  /** @param {unknown} value @param {string} label */
  function requireNonemptyString(value, label) {
    if (typeof value !== "string" || !value.trim()) {
      throw new TypeError(`Shortcut command requires ${label}`);
    }
  }

  /** @param {ShortcutCommand} descriptor */
  function validateCommand(descriptor) {
    if (!descriptor || typeof descriptor !== "object") {
      throw new TypeError("Shortcut command must be an object");
    }
    requireNonemptyString(descriptor.id, "an id");
    requireNonemptyString(descriptor.scope, "a scope");
    requireNonemptyString(descriptor.group, "a group");
    if (!GROUP_DEFINITIONS[/** @type {string} */ (descriptor.group)]) {
      throw new TypeError(`Unknown shortcut group: ${descriptor.group}`);
    }
    if (typeof descriptor.handler !== "function") {
      throw new TypeError("Shortcut command requires a handler");
    }
    if (typeof descriptor.order !== "number" || !Number.isFinite(descriptor.order)) {
      throw new TypeError("Shortcut command requires an explicit numeric order");
    }
    if (!Array.isArray(descriptor.bindings) || descriptor.bindings.length === 0) {
      throw new TypeError("Shortcut command requires bindings");
    }
    descriptor.bindings.map((binding) => normalizeBinding(binding));
    const surfaces = descriptor.surfaces;
    if (!surfaces || typeof surfaces !== "object" || Object.keys(surfaces).length === 0) {
      throw new TypeError("Shortcut command requires at least one presentation surface");
    }
    if (Object.values(surfaces).some((mode) => mode !== "active" && mode !== "always")) {
      throw new TypeError("Shortcut presentation surfaces must be active or always");
    }
    const copy = descriptor.copy;
    if (!copy || typeof copy !== "object") {
      throw new TypeError("Presented shortcut command requires copy");
    }
    requireNonemptyString(copy.action, "action copy");
    requireNonemptyString(copy.description, "description copy");
    requireNonemptyString(copy.hint, "hint copy");
    if (descriptor.control !== undefined && typeof descriptor.control.connect !== "function") {
      throw new TypeError("Shortcut control binding requires connect()");
    }
    return true;
  }

  /**
   * @param {{document?: Document}} [options]
   */
  function create(options = {}) {
    const hostDocument = options.document || window.document;
    if (!hostDocument) {
      throw new Error("Shortcut registry requires a document");
    }
    /** @type {Map<string, ShortcutEntry>} */
    const commands = new Map();
    /** @type {Array<{exclusive: boolean, scope: string, token: symbol}>} */
    const activations = [];
    /** @type {Set<(event: ShortcutEvent) => void>} */
    const subscribers = new Set();
    let disposed = false;
    let batchDepth = 0;
    /** @type {ShortcutEvent[]} */
    let batchedEvents = [];

    /** @param {ShortcutEvent} event */
    function deliver(event) {
      for (const listener of subscribers) {
        listener(event);
      }
    }

    /** @param {ShortcutEvent} event */
    function publish(event) {
      if (batchDepth > 0) {
        batchedEvents.push(event);
      } else {
        deliver(event);
      }
    }

    /**
     * Run `work` and publish what it changed once, when the outermost batch
     * ends: one event of its own when it changed one thing, otherwise a `batch`
     * event naming each kind it contained. What a failed batch changed is
     * still published.
     *
     * @template T
     * @param {() => T} work
     * @returns {T}
     */
    function batch(work) {
      batchDepth += 1;
      try {
        return work();
      } finally {
        batchDepth -= 1;
        if (batchDepth === 0 && batchedEvents.length > 0) {
          const events = batchedEvents;
          batchedEvents = [];
          deliver(
            events.length === 1
              ? events[0]
              : Object.freeze({
                  kind: "batch",
                  kinds: Object.freeze([...new Set(events.map((event) => event.kind))]),
                }),
          );
        }
      }
    }

    // From highest to lowest: activated scopes, most recent first, until an
    // exclusive modal; then `global`; then the permanent scopes below it. A
    // permanent scope lets a letter mean one thing in `global` while that
    // command is available and fall through to another otherwise, as the
    // stack's P does to the Preview tab's.
    function activeLayers() {
      /** @type {string[]} */
      const layers = [];
      for (let index = activations.length - 1; index >= 0; index -= 1) {
        const activation = activations[index];
        if (!layers.includes(activation.scope)) {
          layers.push(activation.scope);
        }
        if (activation.exclusive) {
          return layers;
        }
      }
      for (const scope of PERMANENT_SCOPES) {
        if (!layers.includes(scope)) {
          layers.push(scope);
        }
      }
      return layers;
    }

    /** @param {ShortcutCommand} descriptor */
    function register(descriptor) {
      if (disposed) {
        throw new Error("Shortcut registry is disposed");
      }
      validateCommand(descriptor);
      if (commands.has(descriptor.id)) {
        throw new TypeError(`Duplicate shortcut command id: ${descriptor.id}`);
      }
      const signatures = descriptor.bindings.map((binding) => bindingSignature(binding));
      for (const entry of commands.values()) {
        if (entry.descriptor.scope !== descriptor.scope) {
          continue;
        }
        const existing = new Set(
          entry.descriptor.bindings.map((binding) => bindingSignature(binding)),
        );
        const collision = signatures.find((signature) => existing.has(signature));
        if (collision) {
          throw new TypeError(
            `Duplicate shortcut binding in scope ${descriptor.scope}: ${collision}`,
          );
        }
      }
      const bindings = Object.freeze(
        descriptor.bindings.map((binding) => normalizeBinding(binding)),
      );
      const control = descriptor.control
        ? Object.freeze({ connect: descriptor.control.connect })
        : undefined;
      /** @type {Readonly<ShortcutPresentation>} */
      const presentation = Object.freeze({
        bindings: describeBindings(bindings),
        commandIds: Object.freeze([descriptor.id]),
        control,
        copy: Object.freeze({ ...descriptor.copy }),
        group: descriptor.group,
        id: descriptor.id,
        scope: descriptor.scope,
        surfaces: Object.freeze({ ...descriptor.surfaces }),
      });
      commands.set(descriptor.id, {
        descriptor: { ...descriptor, bindings },
        order: descriptor.order,
        presentation,
      });
      publish(Object.freeze({ commandId: descriptor.id, kind: "registration" }));
      let active = true;
      return () => {
        if (!active) {
          return;
        }
        active = false;
        commands.delete(descriptor.id);
        publish(Object.freeze({ commandId: descriptor.id, kind: "registration" }));
      };
    }

    /** @param {string} scope @param {{exclusive?: boolean}} [activationOptions] */
    function activateScope(scope, activationOptions = {}) {
      requireNonemptyString(scope, "an activation scope");
      const activation = {
        exclusive: Boolean(activationOptions.exclusive),
        scope,
        token: Symbol(scope),
      };
      activations.push(activation);
      publish(Object.freeze({ kind: "scope", scope }));
      let active = true;
      return () => {
        if (!active) {
          return;
        }
        active = false;
        const index = activations.findIndex((candidate) => candidate.token === activation.token);
        if (index >= 0) {
          activations.splice(index, 1);
          publish(Object.freeze({ kind: "scope", scope }));
        }
      };
    }

    /** @param {ShortcutCommand} descriptor @param {Record<string, unknown>} context */
    function runDescriptor(descriptor, context) {
      if (typeof descriptor.available === "function" && !descriptor.available(context)) {
        return false;
      }
      return descriptor.handler(context) === true;
    }

    /** @param {string} commandId @param {Record<string, unknown>} [context] */
    function invoke(commandId, context = {}) {
      const entry = commands.get(commandId);
      if (!entry || !activeLayers().includes(entry.descriptor.scope)) {
        return false;
      }
      return runDescriptor(entry.descriptor, context);
    }

    /**
     * One dispatch pass over the active layers, highest first. A descriptor
     * whose handler declines leaves the event to the next match. Returns
     * whether any live binding matched, handled or not.
     *
     * @param {KeyboardEvent} event
     * @param {{physical?: boolean}} matchOptions
     */
    function dispatch(event, matchOptions) {
      const editable = isEditableTarget(event.target);
      let matched = false;
      for (const scope of activeLayers()) {
        for (const entry of commands.values()) {
          const descriptor = entry.descriptor;
          if (
            descriptor.scope !== scope ||
            (event.repeat && descriptor.repeat !== true) ||
            (editable && descriptor.allowInEditable !== true) ||
            !descriptor.bindings.some((binding) =>
              eventMatchesBinding(event, binding, matchOptions),
            )
          ) {
            continue;
          }
          matched = true;
          if (runDescriptor(descriptor, { event, trigger: null })) {
            event.preventDefault();
            return true;
          }
        }
      }
      return matched;
    }

    /** @param {KeyboardEvent} event */
    function handleKeydown(event) {
      if (event.defaultPrevented || event.isComposing) {
        return;
      }
      // The character typed decides first. Only a character that matched
      // nothing, and is not itself a digit, falls back to its digit-row key.
      if (!dispatch(event, {}) && !isDigitKey(event.key)) {
        dispatch(event, { physical: true });
      }
    }

    /** @param {string} commandId */
    function present(commandId) {
      return commands.get(commandId)?.presentation || null;
    }

    /** @param {string} surface @param {{includeInactive?: boolean}} [snapshotOptions] */
    function snapshot(surface, snapshotOptions = {}) {
      const activeScopes = new Set(activeLayers());
      /** @type {Map<string, ShortcutEntry[]>} */
      const grouped = new Map();
      for (const entry of commands.values()) {
        const mode = entry.presentation.surfaces[surface];
        if (
          !mode ||
          (!snapshotOptions.includeInactive &&
            mode === "active" &&
            !activeScopes.has(entry.descriptor.scope))
        ) {
          continue;
        }
        const values = grouped.get(entry.descriptor.group) || [];
        values.push(entry);
        grouped.set(entry.descriptor.group, values);
      }
      return Object.freeze(
        Array.from(grouped.entries())
          .sort(([left], [right]) => GROUP_DEFINITIONS[left].order - GROUP_DEFINITIONS[right].order)
          .map(([groupId, entries]) => {
            const presentations = entries
              .sort((left, right) => left.order - right.order)
              .map((entry) => entry.presentation);
            /** @type {Readonly<ShortcutPresentation>[]} */
            const rendered = [];
            for (const presentation of presentations) {
              const previous = rendered.at(-1);
              if (
                surface !== "help" &&
                previous &&
                !previous.control &&
                !presentation.control &&
                previous.copy.hint === presentation.copy.hint
              ) {
                rendered[rendered.length - 1] = Object.freeze({
                  ...previous,
                  bindings: describeBindings([
                    ...previous.commandIds.flatMap(
                      (commandId) => commands.get(commandId)?.descriptor.bindings || [],
                    ),
                    ...presentation.commandIds.flatMap(
                      (commandId) => commands.get(commandId)?.descriptor.bindings || [],
                    ),
                  ]),
                  commandIds: Object.freeze([...previous.commandIds, ...presentation.commandIds]),
                });
              } else {
                rendered.push(presentation);
              }
            }
            return Object.freeze({
              commands: Object.freeze(rendered),
              context: GROUP_DEFINITIONS[groupId].context,
              id: groupId,
              label: GROUP_DEFINITIONS[groupId].label,
            });
          }),
      );
    }

    /** @param {(event: ShortcutEvent) => void} listener */
    function subscribe(listener) {
      subscribers.add(listener);
      return () => subscribers.delete(listener);
    }

    hostDocument.addEventListener("keydown", handleKeydown, true);

    function dispose() {
      if (disposed) {
        return;
      }
      disposed = true;
      hostDocument.removeEventListener("keydown", handleKeydown, true);
      commands.clear();
      activations.length = 0;
      subscribers.clear();
    }

    return Object.freeze({
      activateScope,
      /** @param {HTMLElement} container @param {BindingPresentation} presentation */
      appendBinding: (container, presentation) =>
        appendBinding(hostDocument, container, presentation),
      /** @param {HTMLElement} container @param {string} key */
      appendKey: (container, key) => appendKey(hostDocument, container, key),
      batch,
      describeBindings,
      describeKey,
      dispose,
      invoke,
      present,
      register,
      snapshot,
      subscribe,
    });
  }

  window.MetabrowserKeyboardShortcuts = Object.freeze({
    GROUP_DEFINITIONS,
    KEY_DEFINITIONS,
    appendBinding,
    appendKey,
    bindingSignature,
    create,
    describeBindings,
    describeKey,
    eventMatchesBinding,
    isEditableTarget,
    normalizeBinding,
    validateCommand,
  });
})();
