/** @param {{raw?: unknown}} context */
export function resolveReadme(context) {
  const raw =
    context.raw && typeof context.raw === "object"
      ? /** @type {Record<string, unknown>} */ (context.raw)
      : {};
  const path = typeof raw.readme_path === "string" ? raw.readme_path : "";
  return path ? Object.freeze({ key: path, data: Object.freeze({ path }) }) : null;
}

/** @param {MetabrowserPublicSdk} mb */
export function createReadmePanel(mb) {
  return Object.freeze({
    label: "README",
    placement: /** @type {const} */ ("content"),
    presentation: /** @type {const} */ ("document"),
    printable: true,
    collapsible: true,
    defaultExpanded: true,
    resolve: resolveReadme,
    /** @param {HTMLElement} container @param {{path?: string, raw?: unknown}} context @param {{path: string}} data @param {{signal?: AbortSignal}} options */
    mount(container, context, data, options) {
      const value = data;
      const markdown = mb.builtins.markdown;
      if (!markdown) {
        throw new Error("The Markdown renderer is unavailable.");
      }
      return markdown.mountRendered(
        container,
        { ...context, kind: "markdown", path: value.path },
        // The Overview is already the reader's way around this folder, and
        // the panel stack is its own navigation, so a second one inside the
        // embedded README competes with it rather than helping. Suppressed at
        // the render rather than hidden with host CSS, which would build the
        // sidebar layout and then cover it up. Opening the same README as a
        // file keeps KPress' ordinary thresholds.
        { signal: options.signal, includeToc: "off" },
      );
    },
  });
}
