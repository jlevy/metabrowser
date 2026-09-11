// Persisted document reading-width state.
//
// The server injects the default from metabrowser/settings.py. Keeping the
// normalization and apply transition here makes the settings-menu behavior
// runnable from the command line without maintaining a second test model.

(() => {
  const KEY = "metabrowser.docMaxChars";
  // 45-75 characters is the classic single-column range. The bounds are
  // deliberately wider: the floor still holds a readable column in a narrow
  // pane, and the ceiling is where a line stops being followable at all.
  const MIN = 40;
  const MAX = 160;
  const DEFAULT = Number(window.METABROWSER_SETTINGS?.DOC_MAX_CHARS_DEFAULT);

  if (!Number.isFinite(DEFAULT) || DEFAULT < MIN || DEFAULT > MAX) {
    throw new Error(
      "DOC_MAX_CHARS_DEFAULT must be a finite value within the document-width bounds",
    );
  }

  /** @param {unknown} value */
  function normalize(value) {
    const number = Math.round(Number(value));
    if (!Number.isFinite(number)) {
      return DEFAULT;
    }
    return Math.min(MAX, Math.max(MIN, number));
  }

  /** @param {(key: string) => string | null} readPreference */
  function readStored(readPreference) {
    const raw = readPreference(KEY);
    return raw ? normalize(raw) : DEFAULT;
  }

  /**
   * @param {unknown} value
   * @param {boolean} persist
   * @param {{
   *   input: {value: string} | null,
   *   root: {style: {setProperty(name: string, value: string): void}},
   *   writePreference(key: string, value: string): void,
   * }} dependencies
   */
  function apply(value, persist, dependencies) {
    const normalized = normalize(value);
    dependencies.root.style.setProperty("--doc-max-chars", String(normalized));
    if (persist) {
      dependencies.writePreference(KEY, String(normalized));
    }
    // Only when it differs: writing the value back mid-edit would move the
    // caret, and normalization can legitimately differ from what is typed.
    if (dependencies.input && dependencies.input.value !== String(normalized)) {
      dependencies.input.value = String(normalized);
    }
    return normalized;
  }

  window.MetabrowserDocumentWidth = Object.freeze({
    DEFAULT,
    KEY,
    MAX,
    MIN,
    apply,
    normalize,
    readStored,
  });
})();
