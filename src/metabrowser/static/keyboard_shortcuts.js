// Shared command dispatch and presentation for application keyboard shortcuts.

(() => {
  /** @typedef {"alt" | "control" | "meta" | "shift"} ModifierName */
  /** @typedef {"allow" | "forbid" | "require"} ModifierPolicy */
  /**
   * @typedef {object} ShortcutBinding
   * @property {string} key
   * @property {Partial<Record<ModifierName, ModifierPolicy>>} [modifiers]
   */
  /**
   * @typedef {object} BindingPresentation
   * @property {string} ariaKeyshortcuts
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

  /** @type {readonly ModifierName[]} */
  const MODIFIER_ORDER = Object.freeze(["control", "alt", "shift", "meta"]);
  /** @type {Readonly<Record<ModifierName, keyof KeyboardEvent>>} */
  const MODIFIER_EVENT_FIELDS = Object.freeze({
    alt: "altKey",
    control: "ctrlKey",
    meta: "metaKey",
    shift: "shiftKey",
  });
  /** @type {Readonly<Record<ModifierName, Readonly<{aria: string, spoken: string, visible: string}>>>} */
  const MODIFIER_DEFINITIONS = Object.freeze({
    alt: Object.freeze({ aria: "Alt", spoken: "Alt", visible: "Alt" }),
    control: Object.freeze({ aria: "Control", spoken: "Control", visible: "Ctrl" }),
    meta: Object.freeze({ aria: "Meta", spoken: "Meta", visible: "Meta" }),
    shift: Object.freeze({ aria: "Shift", spoken: "Shift", visible: "Shift" }),
  });

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

  /** @type {Readonly<Record<string, Readonly<{context: string, label: string, order: number}>>>} */
  const GROUP_DEFINITIONS = Object.freeze({
    anywhere: Object.freeze({
      context: "Available outside text fields.",
      label: "Anywhere",
      order: 10,
    }),
    navigation: Object.freeze({
      context: "Available while a file-tree row has focus.",
      label: "Navigation",
      order: 20,
    }),
    "quick-file": Object.freeze({
      context: "Available while Quick File is open.",
      label: "Quick File",
      order: 30,
    }),
    help: Object.freeze({
      context: "Available while Help is open.",
      label: "Help",
      order: 40,
    }),
  });

  /** @param {string} key */
  function keyDefinition(key) {
    const known = KEY_DEFINITIONS[key];
    if (known) {
      return known;
    }
    if (/^[a-z]$/i.test(key)) {
      const letter = key.toUpperCase();
      return Object.freeze({ aria: letter, spoken: letter, visible: letter });
    }
    throw new TypeError(`Unsupported shortcut key: ${key}`);
  }

  /** @param {ShortcutBinding} binding @returns {Readonly<ShortcutBinding>} */
  function normalizeBinding(binding) {
    if (!binding || typeof binding.key !== "string") {
      throw new TypeError("Shortcut bindings require a key");
    }
    const definition = keyDefinition(binding.key);
    const key = /^[a-z]$/i.test(binding.key) ? binding.key.toLowerCase() : binding.key;
    const sourceModifiers = binding.modifiers || {};
    const modifiers = /** @type {Record<ModifierName, ModifierPolicy>} */ ({});
    for (const name of MODIFIER_ORDER) {
      const policy = sourceModifiers[name] || "forbid";
      if (!["allow", "forbid", "require"].includes(policy)) {
        throw new TypeError(`Unsupported ${name} modifier policy: ${policy}`);
      }
      modifiers[name] = policy;
    }
    void definition;
    return Object.freeze({ key, modifiers: Object.freeze(modifiers) });
  }

  /** @param {ShortcutBinding} binding */
  function bindingSignature(binding) {
    const normalized = normalizeBinding(binding);
    return `${normalized.key}|${MODIFIER_ORDER.map(
      (name) => `${name}:${normalized.modifiers?.[name]}`,
    ).join("|")}`;
  }

  /** @param {KeyboardEvent} event @param {ShortcutBinding} binding */
  function eventMatchesBinding(event, binding) {
    const normalized = normalizeBinding(binding);
    const eventKey = /^[a-z]$/i.test(event.key) ? event.key.toLowerCase() : event.key;
    if (eventKey !== normalized.key) {
      return false;
    }
    for (const name of MODIFIER_ORDER) {
      const pressed = Boolean(event[MODIFIER_EVENT_FIELDS[name]]);
      const policy = normalized.modifiers?.[name];
      if ((policy === "require" && !pressed) || (policy === "forbid" && pressed)) {
        return false;
      }
    }
    return true;
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
      const normalized = normalizeBinding(binding);
      const definition = keyDefinition(normalized.key);
      const requiredModifiers = MODIFIER_ORDER.filter(
        (name) => normalized.modifiers?.[name] === "require",
      );
      const keys = [
        ...requiredModifiers.map((name) => MODIFIER_DEFINITIONS[name].visible),
        definition.visible,
      ];
      const spoken = [
        ...requiredModifiers.map((name) => MODIFIER_DEFINITIONS[name].spoken),
        definition.spoken,
      ].join(" plus ");
      const ariaKeys = [
        ...requiredModifiers.map((name) => MODIFIER_DEFINITIONS[name].aria),
        definition.aria,
      ];
      return Object.freeze({
        aria: definition.aria ? ariaKeys.join("+") : "",
        spoken,
        visible: Object.freeze({
          keys: Object.freeze(keys),
          separators: Object.freeze(keys.slice(1).map(() => "+")),
        }),
      });
    });
    return Object.freeze({
      ariaKeyshortcuts: alternatives
        .map((alternative) => alternative.aria)
        .filter(Boolean)
        .join(" "),
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
        const keycap = hostDocument.createElement("kbd");
        keycap.className = "kbd";
        keycap.textContent = key;
        if (complex) {
          keycap.setAttribute("aria-hidden", "true");
        }
        container.append(keycap);
      });
    });
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
    /** @type {Set<(event: Readonly<{kind: string, scope?: string, commandId?: string}>) => void>} */
    const subscribers = new Set();
    let disposed = false;

    /** @param {Readonly<{kind: string, scope?: string, commandId?: string}>} event */
    function publish(event) {
      for (const listener of subscribers) {
        listener(event);
      }
    }

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
      layers.push("global");
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

    /** @param {KeyboardEvent} event */
    function handleKeydown(event) {
      if (event.defaultPrevented || event.isComposing) {
        return;
      }
      for (const scope of activeLayers()) {
        for (const entry of commands.values()) {
          const descriptor = entry.descriptor;
          if (
            descriptor.scope !== scope ||
            (event.repeat && descriptor.repeat !== true) ||
            (isEditableTarget(event.target) && descriptor.allowInEditable !== true) ||
            !descriptor.bindings.some((binding) => eventMatchesBinding(event, binding))
          ) {
            continue;
          }
          if (runDescriptor(descriptor, { event, trigger: null })) {
            event.preventDefault();
            return;
          }
        }
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

    /** @param {(event: Readonly<{kind: string, scope?: string, commandId?: string}>) => void} listener */
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
      describeBindings,
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
    bindingSignature,
    create,
    describeBindings,
    eventMatchesBinding,
    isEditableTarget,
    normalizeBinding,
    validateCommand,
  });
})();
