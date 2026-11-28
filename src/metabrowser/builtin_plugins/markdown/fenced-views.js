import { attachStructuredDisclosure } from "./structured-disclosure.js";

/**
 * Only parser-issued markers are eligible. The original rendered code remains
 * readable until its disclosure is opened.
 * @param {HTMLElement} host
 * @param {string} path
 * @param {string} revision
 * @param {ReadonlyArray<KpressStructuredFence>} fences
 * @param {MetabrowserPublicSdk} mb
 * @param {AbortSignal} lifetime
 */
export function attachFencedViews(host, path, revision, fences, mb, lifetime) {
  if (lifetime.aborted || !mb.filterControls) {
    return;
  }
  const doc = host.ownerDocument;
  const expected = new Set(fences.map((fence) => `#${fence.id}`));
  /** @type {Map<string, HTMLAnchorElement | null>} */
  const matches = new Map();
  for (const link of host.querySelectorAll("pre > code > a[href]")) {
    const href = link.getAttribute("href");
    if (href && expected.has(href)) {
      matches.set(href, matches.has(href) ? null : /** @type {HTMLAnchorElement} */ (link));
    }
  }
  for (const { id, opening_line, format } of fences) {
    const key = `#${id}`;
    const marker = matches.get(key);
    const code = marker?.parentElement?.parentElement;
    if (!marker || code?.localName !== "pre" || !code.parentNode) {
      continue;
    }
    matches.delete(key);
    marker.remove();
    const details = doc.createElement("details");
    details.className = "metabrowser-structured-fence kpress-no-print";
    const summary = doc.createElement("summary");
    summary.className = "section-disclosure-trigger disclosure-toggle";
    const language = format.toUpperCase();
    summary.textContent = `Explore ${language}`;
    details.append(summary);
    code.parentNode.insertBefore(details, code);
    attachStructuredDisclosure(
      details,
      mb,
      {
        label: `${language} code at line ${opening_line}`,
        ext: `.${format}`,
        pages: () => mb.createStructuredPageReader(path, { fenceLine: opening_line, revision }),
      },
      lifetime,
      code,
    );
  }
}
