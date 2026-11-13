// Metabrowser — on-demand loading for vendored browser libraries.
//
// A script in the shell's eager path is fetched, parsed, and evaluated
// whether or not anything uses it, and that cost is invisible in a request
// count. Libraries that are large, narrowly used, or both are published as
// named bundles instead and fetched the first time a consumer asks for one.
// See docs/development.md "Asset Loading Tiers" for which tier an asset
// belongs in and why.
//
// The server publishes the bundles as window.METABROWSER_ASSET_BUNDLES:
// a name maps to the ordered scripts that define it. An entry can promise the
// global it provides or be gated on a global its predecessor installs (a
// Chart.js plugin is inert without Chart). Order matters, so the scripts load
// in sequence.
//
// ensureAsset(name) resolves when the bundle's globals are present. It is
// safe to call from every render: a loaded bundle resolves immediately and
// simultaneous callers share the one in-flight load rather than racing to
// append duplicate <script> tags. Successful entries are retained separately,
// so retrying after a later entry fails never evaluates them twice.

((global) => {
  /** @typedef {{src: string, requires?: string, provides?: string}} AssetEntry */

  /** @type {Set<string>} */
  const loaded = new Set();
  /** @type {Map<string, Promise<void>>} */
  const loading = new Map();
  /** @type {Set<string>} */
  const loadedScripts = new Set();
  /** @type {Map<string, Promise<void>>} */
  const loadingScripts = new Map();

  /** @returns {Record<string, Array<AssetEntry>>} */
  function bundles() {
    const published = global.METABROWSER_ASSET_BUNDLES;
    if (!published || typeof published !== "object") {
      return {};
    }
    return published;
  }

  /**
   * Late arrival has to re-enhance what is already on screen, which is what
   * app.js listens for. Emitted per script so a consumer that only needs the
   * first one does not wait for the rest.
   * @param {string} src
   */
  function notifyLoaded(src) {
    global.dispatchEvent(
      new CustomEvent("metabrowser:optional-asset-loaded", { detail: { src: src } }),
    );
  }

  /**
   * @param {AssetEntry} entry
   * @returns {Promise<void>}
   */
  function loadScript(entry) {
    return new Promise((resolve, reject) => {
      const src = entry.src;
      const script = global.document.createElement("script");
      script.src = src;
      // Sequenced, not parallel: a bundle's later scripts read globals its
      // earlier ones install.
      script.async = false;
      script.onload = () => {
        try {
          assertProvidedGlobal(entry);
        } catch (error) {
          script.remove();
          reject(error);
          return;
        }
        notifyLoaded(src);
        resolve();
      };
      script.onerror = () => {
        script.remove();
        reject(new Error(`Failed to load asset: ${src}`));
      };
      global.document.head.appendChild(script);
    });
  }

  /**
   * A load event says the browser fetched and evaluated a script; it does not
   * prove that the library initialized. Validate an entry's declared public
   * effect before retaining or announcing it.
   * @param {AssetEntry} entry
   */
  function assertProvidedGlobal(entry) {
    if (!entry.provides) {
      return;
    }
    const globals = /** @type {Record<string, unknown>} */ (/** @type {unknown} */ (global));
    if (!globals[entry.provides]) {
      throw new Error(`Asset ${entry.src} did not provide expected global: ${entry.provides}`);
    }
  }

  /**
   * Share and retain each successful script independently of its bundle.
   * A later entry can fail after an earlier module has installed process-wide
   * listeners; retrying that bundle must resume at the failed entry instead of
   * evaluating the successful module again.
   *
   * @param {AssetEntry} entry
   * @returns {Promise<void>}
   */
  function ensureScript(entry) {
    const src = entry.src;
    if (loadedScripts.has(src)) {
      try {
        assertProvidedGlobal(entry);
        return Promise.resolve();
      } catch (error) {
        // A stronger declaration may expose an earlier incomplete load. Do
        // not let the src-only cache turn that missing global into success.
        loadedScripts.delete(src);
        return Promise.reject(error);
      }
    }
    const inFlight = loadingScripts.get(src);
    if (inFlight) {
      return inFlight.then(() => {
        try {
          assertProvidedGlobal(entry);
        } catch (error) {
          // The first caller may have made a weaker src-only declaration.
          // Do not retain that fetch as satisfying a concurrent stronger
          // postcondition; the stronger bundle's first retry must refetch.
          loadedScripts.delete(src);
          throw error;
        }
      });
    }
    const pending = loadScript(entry)
      .then(() => {
        loadedScripts.add(src);
      })
      .finally(() => {
        loadingScripts.delete(src);
      });
    loadingScripts.set(src, pending);
    return pending;
  }

  /**
   * Load the named bundle, once. Resolves when every script in it that still
   * applies has run; rejects if the bundle is unknown or a script fails, so a
   * caller can say so rather than rendering into a surface that will not work.
   * @param {string} name
   * @returns {Promise<void>}
   */
  function ensureAsset(name) {
    if (loaded.has(name)) {
      return Promise.resolve();
    }
    const inFlight = loading.get(name);
    if (inFlight) {
      return inFlight;
    }
    const entries = bundles()[name];
    if (!Array.isArray(entries) || entries.length === 0) {
      return Promise.reject(new Error(`Unknown asset bundle: ${name}`));
    }
    const pending = entries
      .reduce(
        (chain, entry) =>
          chain.then(() => {
            // A gated script whose dependency never appeared is skipped, not
            // failed: the bundle's core still works without its plugins.
            const globals = /** @type {Record<string, unknown>} */ (
              /** @type {unknown} */ (global)
            );
            if (entry.requires && !globals[entry.requires]) {
              return undefined;
            }
            return ensureScript(entry);
          }),
        /** @type {Promise<void>} */ (Promise.resolve()),
      )
      .then(() => {
        loaded.add(name);
      })
      .finally(() => {
        loading.delete(name);
      });
    loading.set(name, pending);
    return pending;
  }

  /** @param {string} name @returns {boolean} */
  function assetLoaded(name) {
    return loaded.has(name);
  }

  global.MetabrowserAssets = {
    ensureAsset: ensureAsset,
    assetLoaded: assetLoaded,
  };
})(window);
