// The PDF card: a PDF's first page as an image, its name, and its page count, drawn where
// a viewer does not belong (a diff's binary change), and the preview the file page shows
// behind its viewer while the viewer loads.
//
// The image comes from the plugin's routes (sidekick.py): `/api/plugin/pdf/preview` says
// whether a preview is ready and where its PNG is, and `/api/plugin/pdf/preview-image`
// serves it. The preview is drawn by PDFium in a bounded child process on the server, and
// for an untrusted source only inside an OS sandbox (threat model T7); where it cannot be
// drawn the card says why and has no image. A card never starts the browser's viewer: it
// holds no `<embed>`, `<object>`, or `<iframe>`, so a diff that shows one starts nothing.
//
// The card asks for its preview when it nears the viewport (an IntersectionObserver),
// and its image loads lazily, so a long diff of PDFs costs one request per card the
// reader scrolls to. Where the platform has no observer it asks at once.

/** Answers of the preview route a card can draw. */
const PREVIEW_ROUTE = "/api/plugin/pdf/preview";

/**
 * How far outside the viewport a card starts asking for its preview: about one screen,
 * so a reader scrolling at reading speed meets a card whose image is already there.
 */
const NEAR_VIEWPORT = "600px 0px";

/**
 * @typedef {{status: "ready", key: string, width: number, height: number, pages: number,
 *   image: string, rendered: boolean}} ReadyPreview
 * @typedef {{status: "unavailable", reason: string, message: string}} UnavailablePreview
 * @typedef {ReadyPreview | UnavailablePreview} PreviewAnswer
 */

/**
 * The preview route's address for a served file (*path*, as the client holds it) or a
 * blob of the served repository (*oid*).
 *
 * @param {{path?: string, oid?: string}} subject
 */
export function previewAddress(subject) {
  if (typeof subject.oid === "string" && subject.oid) {
    return `${PREVIEW_ROUTE}?oid=${encodeURIComponent(subject.oid)}`;
  }
  if (typeof subject.path === "string" && subject.path) {
    return `${PREVIEW_ROUTE}?path=${encodeURIComponent(subject.path)}`;
  }
  throw new TypeError("a PDF preview names a path or an oid");
}

/**
 * The route's answer, or an unavailable one for a request that failed: the card then
 * shows no image, as it does for any other reason.
 *
 * @param {string} address
 * @returns {Promise<PreviewAnswer>}
 */
export async function fetchPreview(address) {
  try {
    const response = await globalThis.fetch(address, { credentials: "same-origin" });
    const body = response.ok ? await response.json() : null;
    if (body && (body.status === "ready" || body.status === "unavailable")) {
      return body;
    }
  } catch {
    // A failed request is a preview that is not there; the card still names the file.
  }
  return { status: "unavailable", reason: "failed", message: "The preview could not be loaded." };
}

/**
 * @param {Document} doc
 * @param {string} tag
 * @param {string} className
 * @param {string} [text]
 */
function element(doc, tag, className, text) {
  const node = doc.createElement(tag);
  node.setAttribute("class", className);
  if (text !== undefined) {
    node.textContent = text;
  }
  return node;
}

/**
 * The image of a ready preview: lazily loaded, sized by the answer so the card holds its
 * place before the PNG arrives, and described for a screen reader.
 *
 * @param {Document} doc
 * @param {ReadyPreview} preview
 * @param {string} className
 * @param {string} alt
 */
export function previewImage(doc, preview, className, alt) {
  const image = element(doc, "img", className);
  image.setAttribute("src", preview.image);
  image.setAttribute("width", String(preview.width));
  image.setAttribute("height", String(preview.height));
  image.setAttribute("loading", "lazy");
  image.setAttribute("decoding", "async");
  image.setAttribute("alt", alt);
  return image;
}

/** @param {number} pages */
function pageCount(pages) {
  return pages === 1 ? "1 page" : `${pages} pages`;
}

/**
 * Call *ask* once, when *target* nears the viewport, or at once without an observer.
 * Returns the observer's disconnect.
 *
 * @param {Element} target
 * @param {() => void} ask
 */
function whenNear(target, ask) {
  const Observer = globalThis.IntersectionObserver;
  if (typeof Observer !== "function") {
    ask();
    return () => {};
  }
  const observer = new Observer(
    (entries) => {
      if (entries.some((entry) => entry.isIntersecting)) {
        observer.disconnect();
        ask();
      }
    },
    { rootMargin: NEAR_VIEWPORT },
  );
  observer.observe(target);
  return () => observer.disconnect();
}

/**
 * Mount a PDF card in *host*: its first page once the preview is ready, the file's name,
 * and its page count, or, when there is no preview, the reason.
 *
 * *links* are the file's actions (an Open or Download link), shown below the name; a card
 * for bytes the page does not serve, such as a side of a diff's change, has none, and the
 * file is reached through its file bar's View file. The image is not a link: every action
 * is a plain link with its own label.
 *
 * @param {HTMLElement} host
 * @param {{path?: string, oid?: string, name: string, links?: HTMLElement[]}} options
 * @returns {{dispose: () => void, ready: Promise<PreviewAnswer | null>}}
 */
export function mountPdfCard(host, options) {
  const doc = host.ownerDocument;
  const address = previewAddress(options);
  const card = element(doc, "figure", "pdf-card");
  card.setAttribute("data-pdf-preview", "pending");
  const page = element(doc, "div", "pdf-card-page");
  const caption = element(doc, "figcaption", "pdf-card-caption");
  const name = element(doc, "span", "pdf-card-name", options.name);
  const facts = element(doc, "span", "pdf-card-facts");
  caption.replaceChildren(name, facts);
  if (options.links && options.links.length > 0) {
    const actions = element(doc, "span", "pdf-card-actions");
    actions.replaceChildren(...options.links);
    caption.append(actions);
  }
  card.replaceChildren(page, caption);
  host.append(card);

  let disposed = false;
  /** @type {(answer: PreviewAnswer | null) => void} */
  let settle = () => {};
  /** @type {Promise<PreviewAnswer | null>} */
  const ready = new Promise((resolve) => {
    settle = resolve;
  });
  const stopWatching = whenNear(card, () => {
    void fetchPreview(address).then((answer) => {
      if (disposed) {
        settle(null);
        return;
      }
      if (answer.status === "ready") {
        card.setAttribute("data-pdf-preview", "ready");
        page.replaceChildren(
          previewImage(doc, answer, "pdf-card-image", `First page of ${options.name}`),
        );
        facts.textContent = pageCount(answer.pages);
      } else {
        card.setAttribute("data-pdf-preview", "unavailable");
        card.setAttribute("data-pdf-preview-reason", answer.reason);
        facts.textContent = answer.message;
      }
      settle(answer);
    });
  });

  return {
    ready,
    dispose() {
      if (disposed) {
        return;
      }
      disposed = true;
      stopWatching();
      // Dropping the address first stops an image still loading.
      for (const image of page.children) {
        image.removeAttribute("src");
      }
      card.remove();
      settle(null);
    },
  };
}
