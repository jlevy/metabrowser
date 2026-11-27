/** @typedef {Parameters<MetabrowserPublicSdk["mountStructuredExcerpt"]>[1]} ExcerptOptions */

/**
 * Keep the Markdown placement independent of the shared view. The original
 * summary stays mounted so keyboard focus survives opening and closing.
 * @param {HTMLDetailsElement} details
 * @param {MetabrowserPublicSdk} mb
 * @param {ExcerptOptions} options
 * @param {AbortSignal} lifetime
 * @param {HTMLElement} [fallback]
 */
export function attachStructuredDisclosure(details, mb, options, lifetime, fallback) {
  const summary = details.querySelector(":scope > summary");
  if (!summary || lifetime.aborted) {
    return;
  }
  const trigger = summary;
  /** @type {(() => void) | undefined} */
  let release;
  function toggle() {
    if (fallback) {
      fallback.hidden = details.open;
    }
    if (!details.open) {
      release?.();
      release = undefined;
      return;
    }
    if (release) {
      return;
    }
    const content = details.ownerDocument.createElement("div");
    details.replaceChildren(trigger, content);
    let closed = false;
    /** @type {{dispose(): void} | undefined} */
    let handle;
    release = () => {
      closed = true;
      handle?.dispose();
      details.replaceChildren(trigger);
    };
    void mb
      .mountStructuredExcerpt(content, options)
      .then((mounted) => {
        if (closed) {
          mounted.dispose();
        } else {
          handle = mounted;
        }
      })
      .catch((error) => {
        if (!closed) {
          content.className = "notice";
          content.dataset.severity = "warning";
          content.setAttribute("role", "status");
          content.textContent = error instanceof Error ? error.message : String(error);
        }
      });
  }
  details.addEventListener("toggle", toggle);
  lifetime.addEventListener(
    "abort",
    () => {
      details.removeEventListener("toggle", toggle);
      release?.();
      if (fallback) {
        fallback.hidden = false;
      }
    },
    { once: true },
  );
  toggle();
}
