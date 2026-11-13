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
   * @property {boolean} [range] The keycaps are the ends of a run of keys, as the
   *   numbers 1 to 9 are, rather than alternatives.
   * @property {string} spoken
   * @property {readonly string[]} visible One keycap label per alternative.
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
   * @property {boolean} [targeted]
   * @property {boolean} [situational] Its bindings are positional, a run of numbers no
   *   control owns, so it is presented as that run rather than as alternatives.
   * @property {(context: Record<string, unknown>) => boolean} [available]
   */
  /** @typedef {"beside" | "inline-end"} BadgePlacement */
  /**
   * One element a command acts on, and the badge it carries while revealed.
   *
   * @typedef {object} ShortcutTargetRecord
   * @property {HTMLElement | null} badge
   * @property {string} commandId
   * @property {HTMLElement} element
   * @property {BadgePlacement} placement
   * @property {number} rank Lower first among live targets, then document order.
   */
  /**
   * @typedef {object} ShortcutTargetHandle
   * @property {() => void} detach
   * @property {(element: HTMLElement) => void} retarget
   */
  /**
   * One situational control the numbers reach: a link or an action that depends on
   * what the screen shows. Its number is its place among the live ones, so it has none
   * of its own.
   *
   * @typedef {object} NumberedRecord
   * @property {() => unknown} activate
   * @property {HTMLElement | null} badge
   * @property {HTMLElement} element
   * @property {BadgePlacement} placement
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
  // Scopes that are always active below the activated ones, in order. `plugin` holds the
  // keys plugin views attach through static/plugin-shortcuts.js, below every shell key.
  const PERMANENT_SCOPES = Object.freeze(["global", "view-tabs", "plugin"]);

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
    "view-tabs": Object.freeze({
      context: "Available while the tabs are shown.",
      label: "View tabs",
      order: 16,
    }),
    controls: Object.freeze({
      context: "Available while the control is shown.",
      label: "Controls",
      order: 18,
    }),
    // The numbers are positional, so Help gives them one row and never a fixed meaning.
    numbered: Object.freeze({
      context: "The numbers are not fixed: each screen numbers its own links and actions.",
      label: "On this screen",
      order: 19,
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

  // The situational numbers: links and actions that depend on what the screen shows take
  // 1, 2, 3, and on in reading order, which is document order in the shell's layout (the
  // navigation pane before the main pane, top to bottom), up to 9. A tenth and later get
  // no key: no 0, no letter, and no wrap-around (docs/design-system.md, "Keyboard
  // Shortcuts").
  const NUMBERED_LIMIT = 9;
  const NUMBERED_COMMAND_ID = "numbered";
  /** @type {readonly ShortcutBinding[]} */
  const NUMBERED_BINDINGS = Object.freeze(
    Array.from({ length: NUMBERED_LIMIT }, (_, index) => Object.freeze({ key: String(index + 1) })),
  );

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
        // Digit1 through Digit9, the keys the situational numbers use.
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

  // Where a badge sits: inside its target over the inline-end padding, or `beside`:
  // over the target's own inline end but positioned through the nearest badge anchor,
  // for an icon button or a target in a container that clips, so the badge covers its
  // own control rather than the text after it (docs/design-system.md, "Keyboard
  // Commands and Help"). The styles are the `── Keyboard keys ──` blocks of styles.css.
  /** @type {ReadonlySet<string>} */
  const BADGE_PLACEMENTS = new Set(["beside", "inline-end"]);
  const BADGE_ANCHOR_SELECTOR = "[data-kbd-badge-anchor]";
  // Node.DOCUMENT_POSITION_FOLLOWING, spelled out so the registry needs no Node global.
  const DOCUMENT_POSITION_FOLLOWING = 4;

  /**
   * Whether a target can take its key now: connected, not `disabled`, outside any
   * `inert` subtree, and visible. Read at dispatch rather than tracked, because the
   * shell hides whole panels through a style change no target hears about.
   *
   * `checkVisibility()` ignores `inert`, so a view staged in the shell's inert,
   * transparent stage would otherwise count beside the one on screen; the inert walk
   * runs on both paths. Without `checkVisibility()`, no ancestor may compute
   * `display: none` and the target may not compute `visibility: hidden`, which it
   * inherits from an ancestor unless it overrides it.
   *
   * @param {HTMLElement} element
   */
  function isTargetLive(element) {
    if (
      !element.isConnected ||
      element.hasAttribute("disabled") ||
      /** @type {{disabled?: unknown}} */ (element).disabled === true
    ) {
      return false;
    }
    for (let node = /** @type {HTMLElement | null} */ (element); node; node = node.parentElement) {
      if (node.inert) {
        return false;
      }
    }
    if (typeof element.checkVisibility === "function") {
      return element.checkVisibility({ visibilityProperty: true });
    }
    const view = element.ownerDocument.defaultView;
    if (!view) {
      return true;
    }
    for (let node = /** @type {HTMLElement | null} */ (element); node; node = node.parentElement) {
      if (view.getComputedStyle(node).display === "none") {
        return false;
      }
    }
    return view.getComputedStyle(element).visibility !== "hidden";
  }

  /** @param {HTMLElement} left @param {HTMLElement} right */
  function precedesInDocument(left, right) {
    return (
      typeof left.compareDocumentPosition === "function" &&
      (left.compareDocumentPosition(right) & DOCUMENT_POSITION_FOLLOWING) !== 0
    );
  }

  /** @param {readonly ShortcutBinding[]} bindings @returns {BindingPresentation} */
  function describeBindings(bindings) {
    if (!Array.isArray(bindings) || bindings.length === 0) {
      throw new TypeError("Presented commands require at least one binding");
    }
    const alternatives = bindings.map((binding) => keyDefinition(normalizeBinding(binding).key));
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
   * The situational numbers as one run, written by its ends: `1` to `9`. No number has
   * a fixed meaning, so no surface lists one alone, and none names a control in
   * `aria-keyshortcuts`; each is announced only through the run's spoken form.
   *
   * @param {readonly ShortcutBinding[]} bindings
   * @returns {BindingPresentation}
   */
  function describeRange(bindings) {
    const ends = [bindings[0], bindings[bindings.length - 1]].map((binding) =>
      keyDefinition(normalizeBinding(binding).key),
    );
    const visible = Object.freeze(ends.map((end) => end.visible));
    const spoken = `${ends[0].spoken} to ${ends[1].spoken}`;
    const run = { ariaKeyshortcuts: "", range: true, spoken, visible };
    return Object.freeze({ ...run, preferred: Object.freeze({ ...run }) });
  }

  /**
   * One keycap per alternative, joined by "or", or a run's two ends joined by a dash.
   * Every binding is a single key, so an alternative is one keycap; a group of them is
   * spoken as one visually hidden phrase, such as "T or slash" or "1 to 9", with its
   * keycaps and separators hidden.
   *
   * @param {Document} hostDocument
   * @param {HTMLElement} container
   * @param {BindingPresentation} presentation
   */
  function appendBinding(hostDocument, container, presentation) {
    const alternatives = presentation.visible.length > 1;
    if (alternatives) {
      const spoken = hostDocument.createElement("span");
      spoken.className = "visually-hidden";
      spoken.textContent = presentation.spoken;
      container.append(spoken);
    }
    presentation.visible.forEach((label, index) => {
      if (index > 0) {
        const separator = hostDocument.createElement("span");
        separator.className = "shortcut-binding-separator";
        separator.textContent = presentation.range ? "–" : "or";
        separator.setAttribute("aria-hidden", "true");
        container.append(separator);
      }
      const keycap = createKeycap(hostDocument, label);
      if (alternatives) {
        keycap.setAttribute("aria-hidden", "true");
      }
      container.append(keycap);
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
    if (descriptor.targeted !== undefined && typeof descriptor.targeted !== "boolean") {
      throw new TypeError("Shortcut command targeted must be a boolean");
    }
    if (descriptor.situational !== undefined && typeof descriptor.situational !== "boolean") {
      throw new TypeError("Shortcut command situational must be a boolean");
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
    // Whether a change inside the current batch left the badges to move, once, as it ends.
    let badgesStale = false;
    /** Each command's attached targets, kept apart from registration: a command
     * re-registered with new copy keeps the elements it acts on.
     * @type {Map<string, ShortcutTargetRecord[]>} */
    const targets = new Map();
    /** @type {Set<(event: KeyboardEvent, handled: boolean) => void>} */
    const keyObservers = new Set();
    // Whether the key reveal shows: badges exist only then (static/key-reveal.js).
    let revealed = false;
    /** The situational controls, in the order they were attached; their numbers come
     * from where they are on screen, read when a number is pressed or shown.
     * @type {NumberedRecord[]} */
    const numbered = [];
    /** Releases the numbers' one command, registered while any control is numbered.
     * @type {(() => void) | null} */
    let releaseNumbered = null;

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
     * event naming each kind it contained. While revealed, the badges move once
     * then too, before the publication, however many changes the batch held.
     * What a failed batch changed is still published.
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
        if (batchDepth === 0 && badgesStale) {
          badgesStale = false;
          followBadges();
        }
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
    // command is available and fall through to another otherwise, and a shell
    // key outrank a plugin key on the same letter.
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
        bindings: descriptor.situational ? describeRange(bindings) : describeBindings(bindings),
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
      for (const record of targets.get(descriptor.id) || []) {
        writeTargetShortcut(record);
      }
      followBadges();
      publish(Object.freeze({ commandId: descriptor.id, kind: "registration" }));
      let active = true;
      return () => {
        if (!active) {
          return;
        }
        active = false;
        commands.delete(descriptor.id);
        for (const record of targets.get(descriptor.id) || []) {
          writeTargetShortcut(record);
        }
        followBadges();
        publish(Object.freeze({ commandId: descriptor.id, kind: "registration" }));
      };
    }

    /**
     * A target carries its command's `aria-keyshortcuts` for as long as both exist,
     * so the key is announced at rest and not only while revealed.
     *
     * @param {ShortcutTargetRecord} record
     */
    function writeTargetShortcut(record) {
      const aria = commands.get(record.commandId)?.presentation.bindings.ariaKeyshortcuts;
      if (aria) {
        record.element.setAttribute("aria-keyshortcuts", aria);
      } else {
        record.element.removeAttribute("aria-keyshortcuts");
      }
    }

    /**
     * The first live target of a command, by rank and then in document order: the one
     * a key runs and the one that carries the badge. The others keep their
     * `aria-keyshortcuts` and wait their turn. Shell targets all rank 0; the plugin
     * facade ranks a letter's targets by which plugin attached it first.
     *
     * @param {string} commandId
     */
    function firstLiveTarget(commandId) {
      /** @type {ShortcutTargetRecord | null} */
      let first = null;
      for (const record of targets.get(commandId) || []) {
        if (
          isTargetLive(record.element) &&
          (!first ||
            record.rank < first.rank ||
            (record.rank === first.rank && precedesInDocument(record.element, first.element)))
        ) {
          first = record;
        }
      }
      return first;
    }

    /**
     * Whether a command would run now, as far as anything but the key can say: its
     * scope is active, its `available()` holds, and a targeted command has a live
     * target. A targeted command with no target at all is not live.
     *
     * @param {ShortcutEntry} entry
     * @param {ReadonlySet<string>} activeScopes
     */
    function entryIsLive(entry, activeScopes) {
      return (
        entryIsReady(entry, activeScopes) &&
        (!entry.descriptor.targeted || firstLiveTarget(entry.descriptor.id) !== null)
      );
    }

    /**
     * Whether a command would run now apart from its targets: its scope is active and
     * its `available()` holds.
     *
     * @param {ShortcutEntry} entry
     * @param {ReadonlySet<string>} activeScopes
     */
    function entryIsReady(entry, activeScopes) {
      const descriptor = entry.descriptor;
      return (
        activeScopes.has(descriptor.scope) &&
        (typeof descriptor.available !== "function" || descriptor.available({}))
      );
    }

    /**
     * Badges follow targets: while revealed, each live command's first live target
     * carries one keycap, and every other target carries none. At rest no target
     * carries one, so nothing about a target's text or layout changes then. Each
     * target's liveness is read once a pass: a ready command's first live target is
     * both what makes it live and the one its badge goes on.
     */
    function reconcileBadges() {
      const activeScopes = new Set(activeLayers());
      for (const [commandId, records] of targets) {
        const entry = commands.get(commandId);
        const chosen =
          revealed && entry && entryIsReady(entry, activeScopes)
            ? firstLiveTarget(commandId)
            : null;
        for (const record of records) {
          if (record === chosen && entry) {
            mountBadge(record, entry.descriptor.bindings[0].key);
          } else {
            unmountBadge(record);
          }
        }
      }
      // The numbers go to the live situational controls in reading order, the first nine,
      // while their command's scope is active: never behind Help or Quick Search.
      const numbers = commands.get(NUMBERED_COMMAND_ID);
      const shown =
        revealed && numbers && activeScopes.has(numbers.descriptor.scope) ? liveNumbered() : [];
      for (const [index, record] of shown.entries()) {
        mountBadge(record, String(index + 1));
      }
      for (const record of numbered) {
        if (!shown.includes(record)) {
          unmountBadge(record);
        }
      }
    }

    /**
     * The live situational controls in reading order, at most nine: the one a number
     * reaches is at that place. Ordered first, so the liveness reads stop at the ninth.
     */
    function liveNumbered() {
      const ordered = [...numbered].sort((left, right) =>
        left.element === right.element
          ? 0
          : precedesInDocument(left.element, right.element)
            ? -1
            : 1,
      );
      /** @type {NumberedRecord[]} */
      const live = [];
      for (const record of ordered) {
        if (live.length === NUMBERED_LIMIT) {
          break;
        }
        if (isTargetLive(record.element)) {
          live.push(record);
        }
      }
      return live;
    }

    /**
     * A change while revealed moves the badges at once, or inside a batch once as the
     * batch ends; at rest there are none to move.
     */
    function followBadges() {
      if (!revealed) {
        return;
      }
      if (batchDepth > 0) {
        badgesStale = true;
      } else {
        reconcileBadges();
      }
    }

    /**
     * One `kbd.kbd.kbd-badge`, hidden from assistive technology, which reads the
     * target's `aria-keyshortcuts` instead. `inline-end` puts it inside the target,
     * which becomes its containing block through `.kbd-badge-host`; `beside` puts it
     * in the nearest badge anchor, at the target's inline end and vertical center,
     * measured once as it mounts. A badge already in place keeps its node, so it does
     * not fade in again when the badges move after a key.
     *
     * @param {{badge: HTMLElement | null, element: HTMLElement, placement: BadgePlacement}} record
     * @param {string} key
     */
    function mountBadge(record, key) {
      const anchor =
        record.placement === "beside"
          ? /** @type {HTMLElement | null} */ (record.element.closest(BADGE_ANCHOR_SELECTOR)) ||
            record.element.parentElement
          : record.element;
      if (!anchor) {
        unmountBadge(record);
        return;
      }
      if (
        record.badge?.isConnected &&
        record.badge.parentElement === anchor &&
        record.badge.textContent === describeKey(key).visible
      ) {
        return;
      }
      unmountBadge(record);
      const badge = appendKey(hostDocument, anchor, key);
      badge.className = "kbd kbd-badge";
      badge.setAttribute("aria-hidden", "true");
      badge.dataset.kbdPlacement = record.placement;
      if (record.placement === "beside") {
        const anchorBox = anchor.getBoundingClientRect();
        const box = record.element.getBoundingClientRect();
        const rtl = hostDocument.defaultView?.getComputedStyle(record.element).direction === "rtl";
        const inline = rtl ? anchorBox.right - box.left : box.right - anchorBox.left;
        badge.style.setProperty("--kbd-badge-inline", `${Math.round(inline)}px`);
        badge.style.setProperty(
          "--kbd-badge-block",
          `${Math.round(box.top + box.height / 2 - anchorBox.top)}px`,
        );
      } else {
        record.element.classList.add("kbd-badge-host");
      }
      record.badge = badge;
    }

    /** @param {{badge: HTMLElement | null, element: HTMLElement}} record */
    function unmountBadge(record) {
      if (!record.badge) {
        return;
      }
      record.badge.remove();
      record.badge = null;
      record.element.classList.remove("kbd-badge-host");
    }

    /**
     * Record `element` as a target of `commandId`: what its key acts on and where its
     * badge goes. The element carries the command's `aria-keyshortcuts` while
     * attached. A component that rebuilds its markup calls `retarget()` with the new
     * element; `detach()` removes the attribute, any badge, and the record, and is
     * idempotent. During a reveal the badge follows at once. A lower `rank` goes
     * first among the command's live targets, ahead of document order.
     *
     * @param {string} commandId
     * @param {HTMLElement} element
     * @param {{placement?: BadgePlacement, rank?: number}} [targetOptions]
     * @returns {Readonly<ShortcutTargetHandle>}
     */
    function attachTarget(commandId, element, targetOptions = {}) {
      if (disposed) {
        throw new Error("Shortcut registry is disposed");
      }
      requireNonemptyString(commandId, "a target command id");
      requireTargetElement(element);
      const placement = targetOptions.placement ?? "inline-end";
      if (!BADGE_PLACEMENTS.has(placement)) {
        throw new TypeError(`Unknown badge placement: ${placement}`);
      }
      const rank = targetOptions.rank ?? 0;
      if (typeof rank !== "number" || !Number.isFinite(rank)) {
        throw new TypeError("A shortcut target's rank must be a finite number");
      }
      /** @type {ShortcutTargetRecord} */
      const record = { badge: null, commandId, element, placement, rank };
      const records = targets.get(commandId) || [];
      records.push(record);
      targets.set(commandId, records);
      writeTargetShortcut(record);
      followBadges();
      publish(Object.freeze({ commandId, kind: "target" }));
      let attached = true;
      return Object.freeze({
        /** @param {HTMLElement} next */
        retarget(next) {
          requireTargetElement(next);
          if (!attached || next === record.element) {
            return;
          }
          unmountBadge(record);
          record.element.removeAttribute("aria-keyshortcuts");
          record.element = next;
          writeTargetShortcut(record);
          followBadges();
          publish(Object.freeze({ commandId, kind: "target" }));
        },
        detach() {
          if (!attached) {
            return;
          }
          attached = false;
          unmountBadge(record);
          record.element.removeAttribute("aria-keyshortcuts");
          const remaining = (targets.get(commandId) || []).filter((value) => value !== record);
          if (remaining.length > 0) {
            targets.set(commandId, remaining);
          } else {
            targets.delete(commandId);
          }
          followBadges();
          publish(Object.freeze({ commandId, kind: "target" }));
        },
      });
    }

    /**
     * Number a situational control: a link or an action that depends on what the screen
     * shows. Its number is its place among the live numbered controls in reading order,
     * 1 to 9, read when a number is pressed or shown, so the same number reaches
     * different controls on different screens and a tenth control has none. The shell
     * and the plugin facade both number through this one call, so no surface picks its
     * own digits. A numbered control carries no `aria-keyshortcuts`, because its number
     * is not its own; Help describes the numbers once. `retarget()` follows a rebuilt
     * control and `detach()` is idempotent, as for `attachTarget()`.
     *
     * @param {HTMLElement} element
     * @param {{activate: () => unknown, placement?: BadgePlacement}} numberOptions
     * @returns {Readonly<ShortcutTargetHandle>}
     */
    function attachNumbered(element, numberOptions) {
      if (disposed) {
        throw new Error("Shortcut registry is disposed");
      }
      requireTargetElement(element);
      const activate = numberOptions?.activate;
      if (typeof activate !== "function") {
        throw new TypeError("A numbered control requires an activate function");
      }
      const placement = numberOptions.placement ?? "inline-end";
      if (!BADGE_PLACEMENTS.has(placement)) {
        throw new TypeError(`Unknown badge placement: ${placement}`);
      }
      /** @type {NumberedRecord} */
      const record = { activate, badge: null, element, placement };
      batch(() => {
        numbered.push(record);
        if (!releaseNumbered) {
          releaseNumbered = register(numberedCommand());
        }
        followBadges();
        publish(Object.freeze({ commandId: NUMBERED_COMMAND_ID, kind: "target" }));
      });
      let attached = true;
      return Object.freeze({
        /** @param {HTMLElement} next */
        retarget(next) {
          requireTargetElement(next);
          if (!attached || next === record.element) {
            return;
          }
          unmountBadge(record);
          record.element = next;
          followBadges();
          publish(Object.freeze({ commandId: NUMBERED_COMMAND_ID, kind: "target" }));
        },
        detach() {
          if (!attached) {
            return;
          }
          attached = false;
          batch(() => {
            unmountBadge(record);
            numbered.splice(numbered.indexOf(record), 1);
            if (numbered.length === 0 && releaseNumbered) {
              const release = releaseNumbered;
              releaseNumbered = null;
              release();
            }
            followBadges();
            publish(Object.freeze({ commandId: NUMBERED_COMMAND_ID, kind: "target" }));
          });
        },
      });
    }

    /**
     * The numbers' one command: `1` to `9` in `global`, presented as one run, which Help
     * lists in its own group as positional. A number reaches the control at its place.
     *
     * @returns {ShortcutCommand}
     */
    function numberedCommand() {
      return {
        // Live while one numbered control is, so a number with nothing to reach leaves the
        // key to the browser.
        available: () => liveNumbered().length > 0,
        bindings: NUMBERED_BINDINGS,
        copy: {
          action: "Numbered links and actions",
          description: "Hold Shift to see what each number opens or runs on this screen.",
          hint: "Numbered",
        },
        group: "numbered",
        handler: (context) => {
          const place = numberOf(context);
          const record = place === null ? undefined : liveNumbered()[place - 1];
          return record !== undefined && record.activate() !== false;
        },
        id: NUMBERED_COMMAND_ID,
        order: 10,
        scope: "global",
        situational: true,
        surfaces: { help: "always" },
      };
    }

    /**
     * Which number a key pressed: the digit typed, or else its digit-row key, as Shift+1
     * types `!` on a US layout. `context.number` names one for `invoke()`.
     *
     * @param {Record<string, unknown>} context
     * @returns {number | null}
     */
    function numberOf(context) {
      if (typeof context.number === "number") {
        return context.number;
      }
      const event = /** @type {{key?: unknown, code?: unknown} | undefined} */ (context.event);
      const typed = typeof event?.key === "string" ? event.key : "";
      const physical = typeof event?.code === "string" ? /^Digit([1-9])$/.exec(event.code) : null;
      const digit = /^[1-9]$/.test(typed) ? typed : physical?.[1];
      return digit === undefined ? null : Number(digit);
    }

    /** @param {unknown} element */
    function requireTargetElement(element) {
      if (
        !element ||
        typeof (/** @type {{setAttribute?: unknown}} */ (element).setAttribute) !== "function"
      ) {
        throw new TypeError("A shortcut target must be an element");
      }
    }

    /**
     * Show or hide every badge, for the key reveal, and publish the change so the
     * strip can show the reveal surface.
     *
     * @param {boolean} next
     */
    function setRevealed(next) {
      if (disposed || revealed === Boolean(next)) {
        return;
      }
      revealed = Boolean(next);
      reconcileBadges();
      publish(Object.freeze({ kind: "reveal" }));
    }

    /**
     * Read every attached target's liveness again and move the badges, after a key
     * the registry handled while revealed: a handler can show or hide a target
     * through a style change that publishes nothing, as the Files tab's `F` shows
     * the filter bar. Publishes a `dispatch` event so the revealed strip follows.
     */
    function refreshBadges() {
      if (disposed || !revealed) {
        return;
      }
      reconcileBadges();
      publish(Object.freeze({ kind: "dispatch" }));
    }

    /**
     * Hear every key after the dispatch loop has decided it, as `(event, handled)`,
     * whichever module registered first: the reveal learns of a key only once its
     * handler has returned. While an observer is registered the registry also hears
     * each `keyup`, passively, and passes it through as unhandled; it dispatches none.
     *
     * @param {(event: KeyboardEvent, handled: boolean) => void} observer
     */
    function observeKeys(observer) {
      if (disposed) {
        throw new Error("Shortcut registry is disposed");
      }
      if (typeof observer !== "function") {
        throw new TypeError("A key observer must be a function");
      }
      keyObservers.add(observer);
      if (keyObservers.size === 1) {
        hostDocument.addEventListener("keyup", handleKeyup, { capture: true, passive: true });
      }
      let observing = true;
      return () => {
        if (!observing) {
          return;
        }
        observing = false;
        keyObservers.delete(observer);
        if (keyObservers.size === 0) {
          hostDocument.removeEventListener("keyup", handleKeyup, true);
        }
      };
    }

    /** @param {KeyboardEvent} event @param {boolean} handled */
    function notifyKeyObservers(event, handled) {
      for (const observer of Array.from(keyObservers)) {
        observer(event, handled);
      }
    }

    /** @param {KeyboardEvent} event */
    function handleKeyup(event) {
      notifyKeyObservers(event, false);
    }

    /** @param {string} scope @param {{exclusive?: boolean}} [activationOptions] */
    function activateScope(scope, activationOptions = {}) {
      requireNonemptyString(scope, "an activation scope");
      if (PERMANENT_SCOPES.includes(scope)) {
        // Always active already, in a fixed order: activating one would lift it above
        // `global`, so a view tab's or a plugin's key would outrank the shell's.
        throw new TypeError(`A permanent scope cannot be activated: ${scope}`);
      }
      const activation = {
        exclusive: Boolean(activationOptions.exclusive),
        scope,
        token: Symbol(scope),
      };
      activations.push(activation);
      followBadges();
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
          followBadges();
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

    /**
     * What a command acts on now, for its handler's `context.target`: its first live
     * target, or null. Undefined for a targeted command with none, which does not run.
     *
     * @param {ShortcutCommand} descriptor
     * @returns {HTMLElement | null | undefined}
     */
    function targetFor(descriptor) {
      const target = targets.has(descriptor.id) ? firstLiveTarget(descriptor.id) : null;
      return descriptor.targeted && !target ? undefined : (target?.element ?? null);
    }

    /** @param {string} commandId @param {Record<string, unknown>} [context] */
    function invoke(commandId, context = {}) {
      const entry = commands.get(commandId);
      if (!entry || !activeLayers().includes(entry.descriptor.scope)) {
        return false;
      }
      const target = targetFor(entry.descriptor);
      if (target === undefined) {
        return false;
      }
      return runDescriptor(entry.descriptor, { target, ...context });
    }

    /**
     * One dispatch pass over the active layers, highest first. A descriptor
     * whose handler declines leaves the event to the next match, and a targeted
     * descriptor with no live target does not match at all. Returns whether a
     * handler acted, whether a live binding matched but every handler declined, or
     * whether nothing matched.
     *
     * @param {KeyboardEvent} event
     * @param {{physical?: boolean}} matchOptions
     * @returns {"handled" | "matched" | "none"}
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
          // Visibility is read here, for the one command whose key matched.
          const target = targetFor(descriptor);
          if (target === undefined) {
            continue;
          }
          matched = true;
          if (runDescriptor(descriptor, { event, target, trigger: null })) {
            event.preventDefault();
            return "handled";
          }
        }
      }
      return matched ? "matched" : "none";
    }

    /** @param {KeyboardEvent} event */
    function handleKeydown(event) {
      let outcome = "none";
      if (!event.defaultPrevented && !event.isComposing) {
        // The character typed decides first. Only a character that matched
        // nothing, and is not itself a digit, falls back to its digit-row key.
        outcome = dispatch(event, {});
        if (outcome === "none" && !isDigitKey(event.key)) {
          outcome = dispatch(event, { physical: true });
        }
      }
      // Observers hear the key once its handler has returned, handled or not.
      if (keyObservers.size > 0) {
        notifyKeyObservers(event, outcome === "handled");
      }
    }

    /** @param {string} commandId */
    function present(commandId) {
      return commands.get(commandId)?.presentation || null;
    }

    /**
     * Whether a registered command would run now; see `entryIsLive`.
     *
     * @param {string} commandId
     */
    function isLive(commandId) {
      const entry = commands.get(commandId);
      return entry !== undefined && entryIsLive(entry, new Set(activeLayers()));
    }

    /**
     * The element a command would act on now, its first live target, or null.
     *
     * @param {string} commandId
     */
    function liveTarget(commandId) {
      return firstLiveTarget(commandId)?.element ?? null;
    }

    /**
     * Whether a live command in an active layer above `scope` is bound to `key`, so the
     * key would reach that command first. The plugin facade asks it, so that a shell
     * key outranks a plugin key on the badges and the strip as it does at dispatch.
     *
     * @param {string} scope
     * @param {string} key
     */
    function heldAbove(scope, key) {
      const layers = activeLayers();
      const at = layers.indexOf(scope);
      const above = new Set(at < 0 ? layers : layers.slice(0, at));
      const wanted = normalizeBinding({ key }).key;
      for (const entry of commands.values()) {
        if (
          above.has(entry.descriptor.scope) &&
          entry.descriptor.bindings.some((binding) => binding.key === wanted) &&
          entryIsLive(entry, above)
        ) {
          return true;
        }
      }
      return false;
    }

    /**
     * A surface's commands by group. `live` keeps only the commands that would run
     * now (`isLive`), which the `reveal` surface always does: it shows what the keys
     * under a held Shift reach. Help never reads live, because opening it makes
     * every target behind it `inert`.
     *
     * @param {string} surface
     * @param {{includeInactive?: boolean, live?: boolean}} [snapshotOptions]
     */
    function snapshot(surface, snapshotOptions = {}) {
      const activeScopes = new Set(activeLayers());
      const live = snapshotOptions.live === true || surface === "reveal";
      /** @type {Map<string, ShortcutEntry[]>} */
      const grouped = new Map();
      for (const entry of commands.values()) {
        const mode = entry.presentation.surfaces[surface];
        if (
          !mode ||
          (!snapshotOptions.includeInactive &&
            mode === "active" &&
            !activeScopes.has(entry.descriptor.scope)) ||
          (live && !entryIsLive(entry, activeScopes))
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
                !previous.bindings.range &&
                !presentation.bindings.range &&
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
      if (keyObservers.size > 0) {
        hostDocument.removeEventListener("keyup", handleKeyup, true);
      }
      keyObservers.clear();
      revealed = false;
      for (const records of targets.values()) {
        for (const record of records) {
          unmountBadge(record);
          record.element.removeAttribute("aria-keyshortcuts");
        }
      }
      targets.clear();
      for (const record of numbered) {
        unmountBadge(record);
      }
      numbered.length = 0;
      releaseNumbered = null;
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
      attachNumbered,
      attachTarget,
      batch,
      describeBindings,
      describeKey,
      dispose,
      heldAbove,
      invoke,
      isLive,
      isRevealed: () => revealed,
      /** @param {HTMLElement} element */
      isTargetLive: (element) => isTargetLive(element),
      /** The controls the numbers reach now, in order: 1 is the first. */
      liveNumbers: () => Object.freeze(liveNumbered().map((record) => record.element)),
      liveTarget,
      observeKeys,
      present,
      refreshBadges,
      register,
      setRevealed,
      snapshot,
      subscribe,
    });
  }

  window.MetabrowserKeyboardShortcuts = Object.freeze({
    GROUP_DEFINITIONS,
    KEY_DEFINITIONS,
    NUMBERED_LIMIT,
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
