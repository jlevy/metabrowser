/** @typedef {{metric: "size" | "files", includeIgnored: boolean}} FolderRollupState */

const PREF_KEY = "folder.rollup";

/** @param {unknown} raw @returns {FolderRollupState} */
export function sanitizeFolderRollupState(raw) {
  const value = raw && typeof raw === "object" ? /** @type {Record<string, unknown>} */ (raw) : {};
  return Object.freeze({
    metric: value.metric === "size" ? "size" : "files",
    includeIgnored: value.includeIgnored !== false,
  });
}

/** @param {MetabrowserPublicSdk} mb */
export function createFolderRollupControls(mb) {
  /** @type {FolderRollupState} */
  let current = sanitizeFolderRollupState(mb.prefs.get(PREF_KEY, null));
  /** @type {Set<(state: FolderRollupState) => void>} */
  const subscribers = new Set();

  function get() {
    return current;
  }

  /** @param {Partial<FolderRollupState>} patch */
  function set(patch) {
    const next = sanitizeFolderRollupState({ ...current, ...patch });
    if (next.metric === current.metric && next.includeIgnored === current.includeIgnored) {
      return;
    }
    current = next;
    mb.prefs.set(PREF_KEY, current);
    for (const subscriber of subscribers) {
      subscriber(current);
    }
  }

  /** @param {(state: FolderRollupState) => void} subscriber */
  function subscribe(subscriber) {
    subscribers.add(subscriber);
    subscriber(current);
    return () => subscribers.delete(subscriber);
  }

  /** @param {HTMLElement} container @param {{metric?: boolean, ignored?: boolean}} [parts] */
  function mount(container, parts = {}) {
    const controls = mb.filterControls;
    if (!controls) {
      throw new Error("metabrowser folder plugin: filter controls are unavailable");
    }
    const filterControls = controls;
    const showMetric = parts.metric !== false;
    const showIgnored = parts.ignored !== false;
    container.classList.add("folder-rollup-controls");

    /** @param {FolderRollupState} state */
    function render(state) {
      container.innerHTML = `${
        showMetric
          ? filterControls.groupHtml({
              key: "folder-rollup-metric",
              select: "one",
              layout: "joined",
              label: "Measure file rollups by",
              options: [
                { value: "files", label: "Files" },
                { value: "size", label: "Bytes" },
              ],
              value: state.metric,
            })
          : ""
      }${
        showIgnored
          ? filterControls.checkHtml({
              key: "folder-rollup-ignored",
              label: "Show ignored",
              checked: state.includeIgnored,
              title: "Include gitignored files",
            })
          : ""
      }`;
    }

    const unsubscribe = subscribe(render);
    const unbind = filterControls.bind(container, {
      onChange(key, value, select) {
        if (
          key === "folder-rollup-metric" &&
          select === "one" &&
          (value === "size" || value === "files")
        ) {
          set({ metric: value });
        }
      },
      onToggle(key, checked) {
        if (key === "folder-rollup-ignored") {
          set({ includeIgnored: checked });
        }
      },
    });
    return () => {
      unsubscribe();
      unbind();
    };
  }

  return Object.freeze({ get, mount, set, subscribe });
}
