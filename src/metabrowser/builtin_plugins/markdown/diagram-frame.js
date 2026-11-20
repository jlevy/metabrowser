// Mermaid in a frame of its own, for diagrams whose source nothing else bounds.
//
// KPress's image placement draws each diagram as an `<img>` of its SVG, which runs nothing
// and loads nothing once drawn; but Mermaid lays the diagram out in a document first, and
// there the diagram's own CSS is live. Measured in headless Chrome against Mermaid 12.3.0
// in KPress's image placement on a page with no Content-Security-Policy, each of these
// loaded its URL while the diagram was laid out: the image shape (`A@{ img: … }`); a
// `themeCSS` set by an `%%{init}%%` directive or by front matter; a `fontFamily`
// directive, or a `cursor: url()` in a `themeCSS`; a state diagram's `classDef`; a class
// diagram's `style`; and a `block-beta` diagram's `style`, though only from the page's own
// origin. A page under the untrusted policy (`untrusted_shell_csp` in capabilities.py)
// bounds them by its `img-src`; a folder's page served trusted has no policy at all.
//
// So a diagram from untrusted text on any page is laid out here instead: in an
// `about:srcdoc` frame whose own policy, set by a `<meta>` before anything in it loads,
// admits this module's entry and the vendored Mermaid directory as scripts, inline style,
// and `data:` images, and nothing else (`framePolicy`). The page's KPress binding draws as
// it always does, with this frame's Mermaid as its Mermaid: KPress initializes it and asks
// it to render, the frame lays the diagram out under the frame's policy and returns the
// SVG text, and KPress shows that as an image in the page. The same measurement through
// the frame loaded nothing for any of those sources, in Chrome and in WebKit, and drew the
// rest; an image shape's image is refused, so that diagram shows why and its source. The
// frame's one stylesheet (diagram-frame.css) gives a label the box it has in the page.
//
// The frame is sandboxed to scripts and its own origin, so markup that ever reached its
// document could open no window, submit no form, start no download, and navigate no other
// page. The scripts it runs are this module's entry and Mermaid's, which need the page's
// origin to be imported and to be called.
//
// A frame is a second realm, so Mermaid is evaluated again in it. One frame serves every
// binding that leases it, opened by the first lease that asks for Mermaid and removed when
// the last is released. It also ends if it goes any other way, taken out of the page or
// navigated away. Either way a render still in flight rejects, so KPress's one queue of
// Mermaid calls, which every binding in the page shares, is never held by a frame that is
// gone; and the next lease to ask opens a new frame.

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
 * (Mermaid imports one chunk set per diagram type beside its entry), its stylesheet and
 * inline style, which Mermaid lays its labels out with, and `data:` images; everything
 * else, every image or font a diagram's CSS names among it, falls to `default-src 'none'`.
 *
 * @param {string} entryUrl
 * @param {string} mermaidUrl
 * @param {string} styleUrl
 * @returns {string}
 */
export function framePolicy(entryUrl, mermaidUrl, styleUrl) {
  return [
    "default-src 'none'",
    `script-src ${entryUrl} ${new URL(".", mermaidUrl).href}`,
    `style-src ${styleUrl} 'unsafe-inline'`,
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
 *   api: FrameMermaid | null,
 *   leases: number,
 *   closed: boolean,
 *   close(): void,
 * }} SharedFrame
 */

/** An image shape, `A@{ img: … }`, whose image the frame's policy refuses. */
const IMAGE_SHAPE = /@\{[^}]*\bimg\s*:/;

/** The open frame, while any lease holds it. @type {SharedFrame | null} */
let shared = null;

/**
 * The frame element: sandboxed to scripts and its origin, hidden, out of the tab order,
 * and laid out at KPress's measuring width, its document only the policy, the stylesheet,
 * and the entry.
 *
 * @param {string} entryUrl
 * @param {string} mermaidUrl
 * @param {string} styleUrl
 * @returns {HTMLIFrameElement}
 */
function frameElement(entryUrl, mermaidUrl, styleUrl) {
  const frame = document.createElement("iframe");
  frame.className = "metabrowser-diagram-frame";
  frame.setAttribute("sandbox", "allow-scripts allow-same-origin");
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
    attribute(framePolicy(entryUrl, mermaidUrl, styleUrl)) +
    '"><link rel="stylesheet" href="' +
    attribute(styleUrl) +
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
  /** @type {MutationObserver | null} */
  let watch = null;
  const close = () => {
    if (opened.closed) {
      return;
    }
    closedWith = new Error("The diagram frame closed");
    opened.closed = true;
    closeRenders(closedWith);
    watch?.disconnect();
    if (shared === opened) {
      shared = null;
    }
    frame?.remove();
  };
  const mermaid = (async () => {
    const mermaidUrl = mb.moduleUrl("mermaid");
    if (!mermaidUrl) {
      throw new Error("The Mermaid module bundle is not published");
    }
    const entryUrl = new URL("./diagram-frame-entry.js", import.meta.url).href;
    const styleUrl = new URL("./diagram-frame.css", import.meta.url).href;
    const element = frameElement(entryUrl, mermaidUrl, styleUrl);
    frame = element;
    const loaded = new Promise((resolve) =>
      element.addEventListener("load", resolve, { once: true }),
    );
    document.body.append(element);
    // Taken out of the page, before it loads or after, the frame is gone.
    watch = new MutationObserver(() => {
      if (!element.isConnected) {
        close();
      }
    });
    watch.observe(document.body, { childList: true });
    await Promise.race([loaded, closed]);
    const view =
      /** @type {(Window & {metabrowserDiagramFrame?: {load(url: string): Promise<unknown>}}) | null} */ (
        element.contentWindow
      );
    const doc = element.contentDocument;
    if (!view?.metabrowserDiagramFrame || !doc) {
      throw new Error("The diagram frame did not start");
    }
    // Navigated away, or reloaded by a move in the page, its document and Mermaid are gone.
    // Taking the frame out also hides its page, while the removal is still under way, so
    // the frame is closed once that has finished.
    view.addEventListener("pagehide", () => queueMicrotask(close), { once: true });
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
        // is where Mermaid lays the diagram out. Mermaid measures some text in the body
        // instead, a sequence diagram's actor names among it, so the body takes the same
        // face and size, the ones the image draws that text in.
        const into = doc.createElement("div");
        into.style.cssText = /** @type {HTMLElement | undefined} */ (host)?.style?.cssText ?? "";
        Object.assign(doc.body.style, {
          fontFamily: into.style.fontFamily,
          fontSize: into.style.fontSize,
          lineHeight: into.style.lineHeight,
        });
        doc.body.append(into);
        try {
          const result = await Promise.race([api.render(id, text, into), closed]);
          return { svg: String(result.svg) };
        } catch (error) {
          // The browser's own words for a refused image ("The source image cannot be
          // decoded." in Chrome, "Loading error." in WebKit) do not say why.
          if (!closedWith && IMAGE_SHAPE.test(text)) {
            throw new Error(
              "Images in diagrams from untrusted text, such as a pull request's, are not loaded",
              { cause: error },
            );
          }
          throw error;
        } finally {
          into.remove();
        }
      },
    };
    return proxy;
  })();
  /** @type {SharedFrame} */
  const opened = { mermaid, api: null, leases: 0, closed: false, close };
  // Started, its Mermaid is there to configure at once (`leaseDiagramFrame`); a frame
  // that failed to start is not kept, and the next lease opens another.
  mermaid.then((api) => {
    opened.api = api;
  }, close);
  return opened;
}

/**
 * A lease on the shared frame's Mermaid, for one KPress binding. `mermaid()` resolves,
 * once the frame has started, to the lease's Mermaid, whose calls go to the frame's: the
 * open frame, or a new one if none is open or the one this lease held has closed, given
 * the binding's last configuration before it renders. `release()` ends the lease, and the
 * last lease's release removes the frame.
 *
 * Every lease's Mermaid shares the frame's, and KPress queues every binding's Mermaid
 * calls page-wide, so `initialize` reaches the frame when KPress makes it, and a new
 * frame gets the configuration within the render KPress queued.
 *
 * @param {FrameSdk} mb
 * @returns {{mermaid(): Promise<FrameMermaid>, release(): void}}
 */
export function leaseDiagramFrame(mb) {
  /** @type {SharedFrame | null} */
  let held = null;
  let released = false;
  /** @type {Record<string, unknown> | null} */
  let config = null;
  /** The frame's Mermaid that has the binding's configuration. @type {FrameMermaid | null} */
  let configured = null;
  const frameMermaid = () => {
    if (released) {
      return Promise.reject(new Error("The diagram frame's lease was released"));
    }
    if (!held || held.closed) {
      shared ??= openFrame(mb);
      held = shared;
      held.leases += 1;
    }
    return held.mermaid;
  };
  /** @type {FrameMermaid} */
  const mermaid = {
    initialize(next) {
      config = next;
      configured = held && !held.closed ? held.api : null;
      configured?.initialize?.(next);
    },
    async render(id, text, host) {
      const api = await frameMermaid();
      if (config && configured !== api) {
        api.initialize?.(config);
        configured = api;
      }
      return api.render(id, text, host);
    },
  };
  return {
    mermaid: () => frameMermaid().then(() => mermaid),
    release() {
      if (released) {
        return;
      }
      released = true;
      if (held) {
        held.leases -= 1;
        if (held.leases === 0) {
          held.close();
        }
        held = null;
      }
    },
  };
}
