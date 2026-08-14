/** @typedef {{metric: "size" | "files", includeIgnored: boolean}} FolderRollupState */

const PREF_KEY = "folder.rollup";
const LEGACY_PREF_KEY = "folder.treemap";

/** @param {unknown} raw @returns {FolderRollupState} */
export function sanitizeFolderRollupState(raw) {
  const value = raw && typeof raw === "object" ? /** @type {Record<string, unknown>} */ (raw) : {};
  return Object.freeze({
    metric: value.metric === "size" ? "size" : "files",
    includeIgnored: value.includeIgnored === true,
  });
}

/** @param {MetabrowserPublicSdk} mb */
export function createFolderRollupControls(mb) {
  const currentPreference = mb.prefs.get(PREF_KEY, null);
  const legacyPreference = currentPreference === null ? mb.prefs.get(LEGACY_PREF_KEY, null) : null;
  /** @type {FolderRollupState} */
  let current = sanitizeFolderRollupState(currentPreference ?? legacyPreference);
  if (currentPreference === null && legacyPreference !== null) {
    mb.prefs.set(PREF_KEY, current);
  }
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

  /** @param {HTMLElement} container */
  function mount(container) {
    const controls = mb.filterControls;
    if (!controls) {
      throw new Error("metabrowser folder plugin: filter controls are unavailable");
    }
    const filterControls = controls;
    container.classList.add("folder-rollup-controls");

    /** @param {FolderRollupState} state */
    function render(state) {
      container.innerHTML =
        filterControls.groupHtml({
          key: "folder-rollup-metric",
          select: "one",
          layout: "joined",
          label: "Measure file rollups by",
          options: [
            { value: "files", label: "Files" },
            { value: "size", label: "Bytes" },
          ],
          value: state.metric,
        }) +
        filterControls.checkHtml({
          key: "folder-rollup-ignored",
          label: "Show ignored",
          checked: state.includeIgnored,
          title: "Include gitignored files",
        });
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
