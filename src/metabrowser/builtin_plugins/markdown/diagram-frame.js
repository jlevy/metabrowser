// Mermaid in a frame of its own, for diagrams whose source nothing else bounds.
//
// KPress's image placement draws each diagram as an `<img>` of its SVG, which runs nothing
// and loads nothing once drawn; but Mermaid lays the diagram out in a document first, and
// there the diagram's own CSS is live. Measured in headless Chrome against Mermaid 12.3.0
// in KPress's image placement on a page with no Content-Security-Policy, each of these
// loaded its URL while the diagram was laid out: the image shape (`A@{ img: … }`); a
// `themeCSS` set by an `%%{init}%%` directive or by front matter; a `fontFamily`
// directive; a state diagram's `classDef`; and a `block-beta` diagram's `style`. A page
// under the untrusted policy (`untrusted_shell_csp` in capabilities.py) bounds them by
// its `img-src`; a folder's page served trusted has no policy at all.
//
// So a diagram from untrusted text on any page is laid out here instead: in an
// `about:srcdoc` frame whose own policy, set by a `<meta>` before anything in it loads,
// admits this module's entry and the vendored Mermaid directory as scripts, inline style,
// and `data:` images, and nothing else (`framePolicy`). The page's KPress binding draws as
// it always does, with this frame's Mermaid as its Mermaid: KPress initializes it and asks
// it to render, the frame lays the diagram out under the frame's policy and returns the
// SVG text, and KPress shows that as an image in the page. The same measurement through
// the frame loaded nothing for any of those sources, and drew the rest; an image shape's
// image is refused, so that diagram shows its error and source.
//
// A frame is a second realm, so Mermaid is evaluated again in it. One frame serves every
// binding that leases it, opened by the first lease that asks for Mermaid and removed when
// the last is released; a render still in flight then rejects, so KPress's one queue of
// Mermaid calls is never held by a frame that is gone.

/**
 * The parts of Mermaid's API KPress's image placement calls.
 *
 * @typedef {{
 *   initialize?(config: Record<string, unknown>): void,
 *   render(id: string, text: string, host?: Element): Promise<{svg: string}>,
 * }} FrameMermaid
 */

/**
 * @typedef {{moduleUrl(name: string): string | null}} FrameSdk
 */

/**
 * The frame's Content-Security-Policy: its entry and the Mermaid directory as scripts
 * (Mermaid imports one chunk set per diagram type beside its entry), inline style, which
 * Mermaid lays its labels out with, and `data:` images; everything else, every image or
 * font a diagram's CSS names among it, falls to `default-src 'none'`.
 *
 * @param {string} entryUrl
 * @param {string} mermaidUrl
 * @returns {string}
 */
export function framePolicy(entryUrl, mermaidUrl) {
  return [
    "default-src 'none'",
    `script-src ${entryUrl} ${new URL(".", mermaidUrl).href}`,
    "style-src 'unsafe-inline'",
    "img-src data:",
    "base-uri 'none'",
    "form-action 'none'",
  ].join("; ");
}

/** @param {string} value */
function attribute(value) {
  return value
    .replace(/&/g, "&amp;")
    .replace(/"/g, "&quot;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
}

/**
 * @typedef {{
 *   mermaid: Promise<FrameMermaid>,
 *   leases: number,
 *   close(): void,
 * }} SharedFrame
 */

/** The open frame, while any lease holds it. @type {SharedFrame | null} */
let shared = null;

/**
 * The frame element: hidden, out of the tab order, and laid out at KPress's measuring
 * width, its document only the policy and the entry.
 *
 * @param {string} entryUrl
 * @param {string} mermaidUrl
 * @returns {HTMLIFrameElement}
 */
function frameElement(entryUrl, mermaidUrl) {
  const frame = document.createElement("iframe");
  frame.className = "metabrowser-diagram-frame";
  frame.tabIndex = -1;
  frame.setAttribute("aria-hidden", "true");
  Object.assign(frame.style, {
    position: "fixed",
    left: "-100000px",
    top: "0",
    width: "1200px",
    height: "800px",
    border: "0",
    visibility: "hidden",
  });
  // The policy comes first, so it holds before the entry, or anything else, loads.
  frame.srcdoc =
    '<!doctype html><html><head><meta http-equiv="Content-Security-Policy" content="' +
    attribute(framePolicy(entryUrl, mermaidUrl)) +
    '"><script type="module" src="' +
    attribute(entryUrl) +
    '"></script></head><body></body></html>';
  return frame;
}

/**
 * Open the frame and resolve to its Mermaid, laid out in it.
 *
 * @param {FrameSdk} mb
 * @returns {SharedFrame}
 */
function openFrame(mb) {
  /** @type {HTMLIFrameElement | null} */
  let frame = null;
  /** @type {Error | null} */
  let closedWith = null;
  /** @type {(reason: Error) => void} */
  let closeRenders = () => {};
  /** @type {Promise<never>} */
  const closed = new Promise((_, reject) => {
    closeRenders = reject;
  });
  closed.catch(() => {});
  const mermaid = (async () => {
    const mermaidUrl = mb.moduleUrl("mermaid");
    if (!mermaidUrl) {
      throw new Error("The Mermaid module bundle is not published");
    }
    const entryUrl = new URL("./diagram-frame-entry.js", import.meta.url).href;
    const element = frameElement(entryUrl, mermaidUrl);
    frame = element;
    const loaded = new Promise((resolve) =>
      element.addEventListener("load", resolve, { once: true }),
    );
    document.body.append(element);
    await Promise.race([loaded, closed]);
    const view =
      /** @type {(Window & {metabrowserDiagramFrame?: {load(url: string): Promise<unknown>}}) | null} */ (
        element.contentWindow
      );
    const doc = element.contentDocument;
    if (!view?.metabrowserDiagramFrame || !doc) {
      throw new Error("The diagram frame did not start");
    }
    const namespace = /** @type {{default?: FrameMermaid}} */ (
      await Promise.race([view.metabrowserDiagramFrame.load(mermaidUrl), closed])
    );
    const api = namespace.default;
    if (!api || typeof api.render !== "function") {
      throw new TypeError("The Mermaid module has no render function");
    }
    /** @type {FrameMermaid} */
    const proxy = {
      initialize(config) {
        // Mermaid's configuration, as the frame's own objects.
        api.initialize?.(view.structuredClone(config));
      },
      async render(id, text, host) {
        if (closedWith) {
          throw closedWith;
        }
        // KPress's measuring host carries Mermaid's face and size; its copy in the frame
        // is where Mermaid lays the diagram out.
        const into = doc.createElement("div");
        into.style.cssText = /** @type {HTMLElement | undefined} */ (host)?.style?.cssText ?? "";
        doc.body.append(into);
        try {
          const result = await Promise.race([api.render(id, text, into), closed]);
          return { svg: String(result.svg) };
        } finally {
          into.remove();
        }
      },
    };
    return proxy;
  })();
  /** @type {SharedFrame} */
  const opened = {
    mermaid,
    leases: 0,
    close() {
      closedWith ??= new Error("The diagram frame closed");
      closeRenders(closedWith);
      frame?.remove();
    },
  };
  // A frame that failed to start is not kept: the next lease opens another.
  mermaid.catch(() => {
    if (shared === opened) {
      shared = null;
      opened.close();
    }
  });
  return opened;
}

/**
 * A lease on the shared frame's Mermaid, for one KPress binding: `mermaid()` opens the
 * frame if none is open and resolves to its Mermaid; `release()` ends the lease, and the
 * last lease's release removes the frame.
 *
 * @param {FrameSdk} mb
 * @returns {{mermaid(): Promise<FrameMermaid>, release(): void}}
 */
export function leaseDiagramFrame(mb) {
  /** @type {SharedFrame | null} */
  let held = null;
  let released = false;
  return {
    mermaid() {
      if (released) {
        return Promise.reject(new Error("The diagram frame's lease was released"));
      }
      if (!held) {
        shared ??= openFrame(mb);
        held = shared;
        held.leases += 1;
      }
      return held.mermaid;
    },
    release() {
      if (released) {
        return;
      }
      released = true;
      if (held) {
        held.leases -= 1;
        if (held.leases === 0) {
          if (shared === held) {
            shared = null;
          }
          held.close();
        }
        held = null;
      }
    },
  };
}
