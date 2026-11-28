// Enhance the renderer's frontmatter slot. An inert article has only the sanitized
// prose and TOC, so the host creates that slot itself from the file envelope.
import { attachStructuredDisclosure } from "./structured-disclosure.js";

/**
 * @param {HTMLElement} host
 * @param {string} path
 * @param {Record<string, unknown>} raw
 * @param {MetabrowserPublicSdk} mb
 * @param {AbortSignal} lifetime
 */
export function attachFrontmatter(host, path, raw, mb, lifetime) {
  if (lifetime.aborted || !mb.filterControls) {
    return;
  }
  const doc = host.ownerDocument;
  const article = host.querySelector(":scope > article.kpress-doc");
  if (!article) {
    return;
  }
  let disclosure = /** @type {HTMLDetailsElement | null} */ (
    article.querySelector(
      ":scope > details.kpress-frontmatter:not(.metabrowser-kpress-diagnostics)",
    )
  );
  // Sanitized articles and empty mappings have no KPress disclosure.
  if (!disclosure) {
    disclosure = doc.createElement("details");
    disclosure.className = "kpress-frontmatter kpress-no-print";
    const summary = doc.createElement("summary");
    summary.className = "section-disclosure-trigger disclosure-toggle";
    summary.textContent = "Frontmatter";
    disclosure.append(summary);
    article.insertBefore(disclosure, article.querySelector(":scope > .kpress-doc-layout"));
  }
  const revision = typeof raw.mtime_hash === "string" ? raw.mtime_hash : undefined;
  attachStructuredDisclosure(
    disclosure,
    mb,
    {
      path,
      label: "Frontmatter view",
      ext: ".yaml",
      pages: () => mb.createStructuredPageReader(path, { frontmatter: true, revision }),
      readTree(position) {
        let value = raw.frontmatter;
        for (const segment of position.path) {
          if (!value || typeof value !== "object" || !Object.hasOwn(value, segment)) {
            throw Error("The selected value is unavailable.");
          }
          value = /** @type {Record<string, unknown>} */ (value)[segment];
        }
        return value;
      },
    },
    lifetime,
  );
}
