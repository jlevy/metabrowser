// The plugin shortcut facade: what `window.metabrowser.shortcuts.attach()` does with a key.
//
// A plugin view gives one of its controls a letter key and a badge (docs/plugins.md,
// "Keyboard Shortcuts"). Plugin code can run before the shortcut registry exists: the
// registry arrives with this module in the on-demand `shell-tools` bundle, and the shell
// rebuilds it after a real `pagehide`. So the eager plugin-sdk.js queues each attachment
// made before this module loads, this module takes that queue as it loads, and it keeps
// every attachment for as long as its plugin holds it, replaying them all onto each
// registry the shell attaches with `attachShortcutRegistry`.
//
// It checks what a plugin passes and throws `shortcuts.attach:` for malformed input. A
// letter the shell reserves is refused with one warning per command id, not thrown,
// because the shell may reserve another letter later and that must not break a working
// view. Each letter is one command in the registry's permanent `plugin` scope, below
// every shell key, whose targets are every element attached under that letter; the
// registry checks their liveness at dispatch. A letter two live targets hold is settled
// there and in the reveal: a shell key beats a plugin key, between plugins the earlier
// attachment wins, and within one command id the first target in document order runs.

(() => {
  if (window.MetabrowserPluginShortcuts) {
    return;
  }

  const PLUGIN_SCOPE = "plugin";
  /** @type {ReadonlySet<string>} */
  const GROUPS = new Set(["controls", "view-tabs"]);
  /** @type {ReadonlySet<string>} */
  const OPTIONS = new Set(["activate", "copy", "group", "id", "key", "order", "signal"]);
  const DOTTED_ID = /^[A-Za-z0-9_-]+(\.[A-Za-z0-9_-]+)+$/;
  const LETTER = /^[a-z]$/i;

  /** @typedef {Readonly<{action: string, description: string, hint: string}>} ShortcutCopy */
  /**
   * One plugin control's key, for as long as its plugin holds it.
   *
   * @typedef {object} Attachment
   * @property {() => unknown} activate
   * @property {boolean} attached
   * @property {ShortcutCopy} copy
   * @property {HTMLElement} element
   * @property {"controls" | "view-tabs"} group
   * @property {string} id
   * @property {string} key Lowercase.
   * @property {number} order
   * @property {number} rank When its command id was first attached: earlier wins a letter.
   * @property {boolean} refused The shell reserves its letter, so it is bound nowhere.
   * @property {() => void} release Stop listening to its abort signal.
   */
  /**
   * What one registry holds of the attachments.
   *
   * @typedef {object} Connection
   * @property {Map<string, {commandId: string, holder: string, release: () => void}>} letters
   * @property {MetabrowserPublicShortcutRegistry} registry
   * @property {KeyboardEvent | null} ran The last key this facade's own command ran for.
   * @property {Map<Attachment, MetabrowserPublicShortcutTarget>} targets
   */

  /** @type {Attachment[]} In the order they were attached. */
  const attachments = [];
  /** @type {Set<Connection>} */
  const connections = new Set();
  /** Each command id's rank, kept while it has an attachment. @type {Map<string, number>} */
  const ranks = new Map();
  let nextRank = 0;
  /** @type {Set<string>} */
  const refusalsWarned = new Set();
  /** @type {Set<string>} */
  const lossesWarned = new Set();
  const INERT_HANDLE = Object.freeze({
    detach() {},
    /** @param {HTMLElement} next */
    retarget(next) {
      requireElement(next, "retarget");
    },
  });

  /** @param {string} message */
  function malformed(message) {
    return new TypeError(`shortcuts.attach: ${message}`);
  }

  /**
   * @param {unknown} element
   * @param {string} what
   * @returns {asserts element is HTMLElement}
   */
  function requireElement(element, what) {
    if (!(element instanceof window.HTMLElement)) {
      throw malformed(`${what} needs an HTMLElement`);
    }
  }

  /** @param {Record<string, unknown>} copy @param {string} field */
  function copyField(copy, field) {
    const value = copy[field];
    if (typeof value !== "string" || !value.trim()) {
      throw malformed(`copy.${field} must be a nonempty string`);
    }
    return value;
  }

  /**
   * The spec a plugin passed, checked. The facade fixes everything else a registry
   * command states, so a binding, scope, or surface is malformed input here.
   *
   * @param {unknown} options
   */
  function readSpec(options) {
    if (!options || typeof options !== "object") {
      throw malformed("the second argument must be an options object");
    }
    const spec = /** @type {Record<string, unknown>} */ (options);
    for (const name of Object.keys(spec)) {
      if (!OPTIONS.has(name)) {
        throw malformed(`${name} is not an option; the facade decides it`);
      }
    }
    const { activate, copy, group, id, key, order, signal } = spec;
    if (typeof id !== "string" || !DOTTED_ID.test(id)) {
      throw malformed(`id must be a dotted name such as "diff.layout", not ${String(id)}`);
    }
    if (typeof key !== "string" || !LETTER.test(key)) {
      throw malformed(`${id}: key must be one letter a-z, not ${String(key)}`);
    }
    if (typeof group !== "string" || !GROUPS.has(group)) {
      throw malformed(`${id}: group must be "view-tabs" or "controls", not ${String(group)}`);
    }
    if (typeof order !== "number" || !Number.isFinite(order)) {
      throw malformed(`${id}: order must be a finite number`);
    }
    if (!copy || typeof copy !== "object") {
      throw malformed(`${id}: copy must be {action, description, hint}`);
    }
    const fields = /** @type {Record<string, unknown>} */ (copy);
    if (typeof activate !== "function") {
      throw malformed(`${id}: activate must be a function`);
    }
    if (
      signal !== undefined &&
      (!signal ||
        typeof signal !== "object" ||
        typeof (/** @type {AbortSignal} */ (signal).addEventListener) !== "function")
    ) {
      throw malformed(`${id}: signal must be an AbortSignal`);
    }
    return {
      activate: /** @type {() => unknown} */ (activate),
      copy: Object.freeze({
        action: copyField(fields, "action"),
        description: copyField(fields, "description"),
        hint: copyField(fields, "hint"),
      }),
      group: /** @type {"controls" | "view-tabs"} */ (group),
      id,
      key: key.toLowerCase(),
      order,
      signal: /** @type {AbortSignal | undefined} */ (signal),
    };
  }

  /** Whether the shell reserves `key`, in any context: the table keymap.py serves. */
  function isReserved(/** @type {string} */ key) {
    const reserved = window.METABROWSER_SETTINGS?.RESERVED_SHELL_KEYS;
    return reserved !== undefined && Object.hasOwn(reserved, key);
  }

  /** @param {Set<string>} warned @param {string} id @param {string} message */
  function warnOnce(warned, id, message) {
    if (!warned.has(id)) {
      warned.add(id);
      console.warn(`shortcuts.attach: ${message}`);
    }
  }

  /**
   * Give `element` a letter key: what `metabrowser.shortcuts.attach()` does once this
   * module has loaded, and what it does to each attachment it queued before.
   *
   * @param {unknown} element
   * @param {unknown} options
   * @returns {MetabrowserPublicPluginShortcutHandle}
   */
  function attachShortcut(element, options) {
    requireElement(element, "the element");
    const spec = readSpec(options);
    const sibling = attachments.find((attachment) => attachment.id === spec.id);
    if (
      sibling &&
      (sibling.key !== spec.key ||
        sibling.group !== spec.group ||
        JSON.stringify(sibling.copy) !== JSON.stringify(spec.copy))
    ) {
      throw malformed(`${spec.id} is attached already with another key, group, or copy`);
    }
    if (spec.signal?.aborted) {
      return INERT_HANDLE;
    }
    const refused = isReserved(spec.key);
    if (refused) {
      warnOnce(
        refusalsWarned,
        spec.id,
        `${spec.id} cannot have ${spec.key.toUpperCase()}, which the shell reserves; its control has no key`,
      );
    }
    let rank = ranks.get(spec.id);
    if (rank === undefined) {
      rank = nextRank;
      nextRank += 1;
      ranks.set(spec.id, rank);
    }
    /** @type {Attachment} */
    const attachment = {
      activate: spec.activate,
      attached: true,
      copy: spec.copy,
      element,
      group: spec.group,
      id: spec.id,
      key: spec.key,
      order: spec.order,
      rank,
      refused,
      release: () => {},
    };
    attachments.push(attachment);
    const signal = spec.signal;
    if (signal) {
      const onAbort = () => detachAttachment(attachment);
      signal.addEventListener("abort", onAbort, { once: true });
      attachment.release = () => signal.removeEventListener("abort", onAbort);
    }
    if (!refused) {
      for (const connection of connections) {
        syncLetter(connection, attachment.key);
      }
    }
    return Object.freeze({
      /** @param {HTMLElement} next */
      retarget(next) {
        requireElement(next, "retarget");
        retargetAttachment(attachment, next);
      },
      detach() {
        detachAttachment(attachment);
      },
    });
  }

  /**
   * Move an attachment's key and badge to `next`, after its control rebuilt its markup.
   * The same element again is a control that moved, as a tab bar put back: badges are
   * read again at once if the reveal shows.
   *
   * @param {Attachment} attachment
   * @param {HTMLElement} next
   */
  function retargetAttachment(attachment, next) {
    if (!attachment.attached) {
      return;
    }
    if (next === attachment.element) {
      for (const connection of connections) {
        if (connection.targets.has(attachment)) {
          connection.registry.refreshBadges();
        }
      }
      return;
    }
    attachment.element = next;
    for (const connection of connections) {
      connection.targets.get(attachment)?.retarget(next);
    }
  }

  /** @param {Attachment} attachment */
  function detachAttachment(attachment) {
    if (!attachment.attached) {
      return;
    }
    attachment.attached = false;
    attachment.release();
    attachments.splice(attachments.indexOf(attachment), 1);
    if (!attachments.some((other) => other.id === attachment.id)) {
      ranks.delete(attachment.id);
    }
    for (const connection of connections) {
      connection.registry.batch(() => {
        connection.targets.get(attachment)?.detach();
        connection.targets.delete(attachment);
        if (!attachment.refused) {
          syncLetter(connection, attachment.key);
        }
      });
    }
  }

  /**
   * Make one registry's command for `letter` match the attachments that hold it: one
   * `plugin`-scope command, registered with the copy of the command id that attached
   * the letter first, whose targets are every element attached under the letter. When
   * that id lets go, the command is registered again with the next one's.
   *
   * @param {Connection} connection
   * @param {string} letter
   */
  function syncLetter(connection, letter) {
    const { registry } = connection;
    registry.batch(() => {
      const holding = attachments.filter(
        (attachment) => attachment.key === letter && !attachment.refused,
      );
      /** @type {Attachment | null} */
      let holder = null;
      for (const attachment of holding) {
        if (!holder || attachment.rank < holder.rank) {
          holder = attachment;
        }
      }
      const held = connection.letters.get(letter);
      if (held && held.holder !== holder?.id) {
        for (const [attachment, target] of connection.targets) {
          if (attachment.key === letter) {
            target.detach();
            connection.targets.delete(attachment);
          }
        }
        held.release();
        connection.letters.delete(letter);
      }
      if (!holder) {
        return;
      }
      let current = connection.letters.get(letter);
      if (!current) {
        const commandId = `plugin.${holder.id}`;
        current = {
          commandId,
          holder: holder.id,
          release: registry.register(letterCommand(connection, letter, holder, commandId)),
        };
        connection.letters.set(letter, current);
      }
      for (const attachment of holding) {
        if (!connection.targets.has(attachment)) {
          connection.targets.set(
            attachment,
            registry.attachTarget(current.commandId, attachment.element, { rank: attachment.rank }),
          );
        }
      }
    });
  }

  /**
   * The registry command for one letter. It is live only while one of its targets is,
   * and while no live shell key in a higher scope holds the letter; Help lists it while
   * the letter has an attachment, live or not, as it lists the shell's view tabs.
   *
   * @param {Connection} connection
   * @param {string} letter
   * @param {Attachment} holder
   * @param {string} commandId
   * @returns {MetabrowserPublicShortcutCommand}
   */
  function letterCommand(connection, letter, holder, commandId) {
    return {
      available: () => !connection.registry.heldAbove(PLUGIN_SCOPE, letter),
      bindings: [{ key: letter }],
      copy: holder.copy,
      group: holder.group,
      handler: (context) => runLetter(connection, letter, context),
      id: commandId,
      order: holder.order,
      scope: PLUGIN_SCOPE,
      surfaces: { help: "always" },
      targeted: true,
    };
  }

  /**
   * Run the attachment whose element the registry chose for this key, its first live
   * target, and warn each other command id that held the letter live beside it.
   *
   * @param {Connection} connection
   * @param {string} letter
   * @param {Record<string, unknown>} context
   */
  function runLetter(connection, letter, context) {
    const chosen = attachments.find(
      (attachment) =>
        attachment.key === letter && !attachment.refused && attachment.element === context.target,
    );
    if (!chosen) {
      return false;
    }
    const event = context.event;
    connection.ran =
      event && typeof event === "object" ? /** @type {KeyboardEvent} */ (event) : null;
    noteLosses(connection, letter, chosen);
    try {
      chosen.activate();
    } catch (error) {
      // A plugin's failure stays its own: the registry still tells its observers.
      console.error(`shortcuts.attach: ${chosen.id} failed to activate`, error);
    }
    return true;
  }

  /**
   * Warn, once each, the command ids whose live targets hold `letter` but lose it: to
   * `winner`, attached earlier, or to a shell key when there is no winner.
   *
   * @param {Connection} connection
   * @param {string} letter
   * @param {Attachment | null} winner
   */
  function noteLosses(connection, letter, winner) {
    for (const attachment of attachments) {
      if (
        attachment.key !== letter ||
        attachment.refused ||
        attachment.id === winner?.id ||
        !connection.registry.isTargetLive(attachment.element)
      ) {
        continue;
      }
      const to = winner ? `${winner.id}, attached earlier` : "a shell key shown beside it";
      warnOnce(
        lossesWarned,
        attachment.id,
        `${attachment.id} loses ${letter.toUpperCase()} to ${to}; only the winner runs`,
      );
    }
  }

  /**
   * While the reveal shows, settle every letter as the badges do: what a held letter's
   * key would run now, and who loses it.
   *
   * @param {Connection} connection
   */
  function noteRevealedLosses(connection) {
    const { registry } = connection;
    if (!registry.isRevealed()) {
      return;
    }
    for (const [letter, held] of connection.letters) {
      if (registry.heldAbove(PLUGIN_SCOPE, letter)) {
        noteLosses(connection, letter, null);
        continue;
      }
      const element = registry.liveTarget(held.commandId);
      const winner = attachments.find(
        (attachment) =>
          attachment.key === letter && !attachment.refused && attachment.element === element,
      );
      if (winner) {
        noteLosses(connection, letter, winner);
      }
    }
  }

  /**
   * Bind every attachment, those made already and those to come, to `registry`, in its
   * `plugin` scope. The shell calls this from `initKeyboardInfrastructure()` for each
   * registry it builds, the first and each one after a `pageshow` rebuild, and calls
   * the returned detach before it disposes that registry.
   *
   * @param {MetabrowserPublicShortcutRegistry} registry
   * @returns {() => void}
   */
  function attachShortcutRegistry(registry) {
    if (!registry || typeof registry.register !== "function") {
      throw new TypeError("attachShortcutRegistry: a shortcut registry is required");
    }
    /** @type {Connection} */
    const connection = { letters: new Map(), ran: null, registry, targets: new Map() };
    connections.add(connection);
    registry.batch(() => {
      const letters = new Set(
        attachments.filter((attachment) => !attachment.refused).map((attachment) => attachment.key),
      );
      for (const letter of letters) {
        syncLetter(connection, letter);
      }
    });
    const unsubscribe = registry.subscribe(() => noteRevealedLosses(connection));
    // A key a higher scope handled while a plugin target held its letter: a loss the
    // plugin's command never hears of, since dispatch stopped above it.
    const unobserve = registry.observeKeys((event, handled) => {
      if (event.type !== "keydown" || !handled || connection.ran === event) {
        return;
      }
      const letter = typeof event.key === "string" ? event.key.toLowerCase() : "";
      if (connection.letters.has(letter)) {
        noteLosses(connection, letter, null);
      }
    });
    let bound = true;
    return function detachShortcutRegistry() {
      if (!bound) {
        return;
      }
      bound = false;
      connections.delete(connection);
      unsubscribe();
      unobserve();
      registry.batch(() => {
        for (const target of connection.targets.values()) {
          target.detach();
        }
        connection.targets.clear();
        for (const held of connection.letters.values()) {
          held.release();
        }
        connection.letters.clear();
      });
    };
  }

  /**
   * Detach every attachment whose element is `container` or inside it: the net under a
   * view's own `dispose()`, which view composition runs when it disposes a container.
   *
   * @param {Node} container
   */
  function releaseWithin(container) {
    for (const attachment of [...attachments]) {
      if (container === attachment.element || container.contains(attachment.element)) {
        detachAttachment(attachment);
      }
    }
  }

  window.MetabrowserPluginShortcuts = Object.freeze({
    attachShortcut,
    attachShortcutRegistry,
    releaseWithin,
  });

  // What plugins attached before this module loaded. A malformed one was a plugin's
  // error when it was made, and no caller is left to throw to, so it is logged.
  const queue = window.MetabrowserPluginHost?.shortcutQueue ?? [];
  for (const queued of queue.splice(0)) {
    if (queued.options === null) {
      continue;
    }
    try {
      queued.handle = attachShortcut(queued.element, queued.options);
    } catch (error) {
      console.error(error);
    }
  }
})();
