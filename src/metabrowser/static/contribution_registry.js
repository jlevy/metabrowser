// Generic deterministic contribution registry.

(() => {
  /**
   * @template T
   * @param {{validate: (id: string, spec: T) => void, compare: (left: Readonly<T & {id: string}>, right: Readonly<T & {id: string}>) => number}} options
   */
  function createContributionRegistry(options) {
    /** @type {Map<string, Readonly<T & {id: string}>>} */
    const entries = new Map();
    return Object.freeze({
      /** @param {string} id @param {T} spec */
      register(id, spec) {
        options.validate(id, spec);
        if (entries.has(id)) {
          throw new Error(`Duplicate contribution: ${id}`);
        }
        const descriptor = Object.freeze(Object.assign({}, spec, { id }));
        entries.set(id, descriptor);
        let registered = true;
        return () => {
          if (registered) {
            registered = false;
            entries.delete(id);
          }
        };
      },
      list() {
        return Object.freeze(Array.from(entries.values()).sort(options.compare));
      },
    });
  }

  window.MetabrowserContributionRegistry = Object.freeze({ createContributionRegistry });
})();
