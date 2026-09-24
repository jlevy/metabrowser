// Reduce rendered Markdown from an untrusted source to a small allowlist of plain markup,
// in the browser. The same rules as src/metabrowser/inert_html.py, which applies them
// first on the server; tests/test_inert_html.py proves the two allowlists are the same.
//
// The page never inserts parsed nodes. `sanitizeHtml` parses into a <template>, whose
// content is inert -- nothing in it loads or runs -- and `sanitizeNodes` builds new nodes
// from the allowlist alone: new elements for allowed tags with only their checked
// attributes, new text, images kept only inside the served tree and otherwise turned
// into links, other tags unwrapped, and the dropped ones gone with their content. No
// class, name, data, style, or event attribute survives, nor any SVG, MathML, media,
// stylesheet, frame, or form, and no id the document wrote: in a document inside the
// served tree each heading gets the anchor github.com would give it, `user-content-`
// and the slug of its text, and a `#name` link becomes `#user-content-name`.
//
// Loaded on demand (`ensureAsset("inert-html")`) by the views that render untrusted
// Markdown: the pull-request page and repository Markdown under the untrusted profile.
// tests/dom/inert-html-session.js runs it from the command line.

(() => {
  const ALLOWED_TAGS = Object.freeze([
    "a",
    "b",
    "blockquote",
    "br",
    "code",
    "dd",
    "del",
    "details",
    "div",
    "dl",
    "dt",
    "em",
    "h1",
    "h2",
    "h3",
    "h4",
    "h5",
    "h6",
    "hr",
    "i",
    "ins",
    "kbd",
    "li",
    "ol",
    "p",
    "pre",
    "s",
    "span",
    "strong",
    "sub",
    "summary",
    "sup",
    "table",
    "tbody",
    "td",
    "tfoot",
    "th",
    "thead",
    "tr",
    "ul",
  ]);
  const DROPPED_WITH_CONTENT = Object.freeze([
    "audio",
    "base",
    "canvas",
    "embed",
    "form",
    "iframe",
    "link",
    "math",
    "meta",
    "noscript",
    "object",
    "option",
    "picture",
    "script",
    "select",
    "source",
    "style",
    "svg",
    "template",
    "textarea",
    "title",
    "track",
    "video",
  ]);
  // The attributes each tag may keep; every value is checked by allowedAttributes,
  // except a heading's id, which is always sanitizeNodes' own anchor.
  const HEADINGS = Object.freeze(["h1", "h2", "h3", "h4", "h5", "h6"]);
  const ALLOWED_ATTRIBUTES = Object.freeze({
    a: Object.freeze(["href", "target", "rel"]),
    img: Object.freeze(["src", "alt"]),
    ol: Object.freeze(["start"]),
    td: Object.freeze(["colspan", "rowspan", "align"]),
    th: Object.freeze(["colspan", "rowspan", "align"]),
    details: Object.freeze(["open"]),
    ...Object.fromEntries(HEADINGS.map((tag) => [tag, Object.freeze(["id"])])),
  });

  // Every heading anchor begins with this, as on github.com: the document's names stay
  // apart from the application's ids and from window properties.
  const ANCHOR_PREFIX = "user-content-";
  // What a GitHub slug drops: all but hyphen, space, and the Unicode word characters
  // (Alphabetic, Mark, Decimal_Number, Connector_Punctuation) github-slugger keeps,
  // spelled by general category as inert_html.py spells them.
  const SLUG_DROPS =
    /[^\p{Letter}\p{Mark}\p{Decimal_Number}\p{Letter_Number}\p{Connector_Punctuation}\u24B6-\u24E9\u{1F130}-\u{1F149}\u{1F150}-\u{1F169}\u{1F170}-\u{1F189} -]/gu;

  /**
   * GitHub's slug of a heading's text: lowercased, word characters, hyphens, and
   * spaces kept, and each space a hyphen.
   *
   * @param {string} text
   */
  function headingSlug(text) {
    return text.toLowerCase().replace(SLUG_DROPS, "").replaceAll(" ", "-");
  }

  /** GitHub's numbering of repeated slugs (github-slugger): `a`, `a-1`, `a-2`. */
  function createAnchors() {
    /** @type {Map<string, number>} */
    const seen = new Map();
    /** @param {string} text */
    return (text) => {
      const original = headingSlug(text);
      let result = original;
      while (seen.has(result)) {
        const count = (seen.get(original) ?? 0) + 1;
        seen.set(original, count);
        result = `${original}-${count}`;
      }
      seen.set(result, 0);
      return ANCHOR_PREFIX + result;
    };
  }

  /**
   * A fragment-only reference as it reaches a heading anchor: `#name` becomes
   * `#user-content-name`, and one already in the namespace stays, as on github.com.
   *
   * @param {string} href
   */
  function fragmentLink(href) {
    const name = href.slice(1);
    return name === "" || name.startsWith(ANCHOR_PREFIX) ? href : `#${ANCHOR_PREFIX}${name}`;
  }

  /**
   * What a browser reads from a URL: ASCII tab and newline removed anywhere, C0
   * controls and spaces trimmed from either end.
   *
   * @param {string} href
   */
  function clean(href) {
    const stripped = href.replace(/[\t\n\r]/g, "");
    let start = 0;
    let end = stripped.length;
    while (start < end && stripped.charCodeAt(start) <= 0x20) {
      start += 1;
    }
    while (end > start && stripped.charCodeAt(end - 1) <= 0x20) {
      end -= 1;
    }
    return stripped.slice(start, end);
  }

  const SCHEME = /^[A-Za-z][A-Za-z0-9+.-]*:/;
  // Two slashes or backslashes in any mix begin another origin's address.
  const OTHER_ORIGIN = /^[/\\]{2}/;

  // The application's own routes, which a document inside the served tree never names:
  // fetching or following one from untrusted markup reaches the application.
  const RESERVED = /^\/(?:api|_debug|raw)(?:[/?#]|$)/i;
  // An escaped slash or backslash, which the server's router reads as a separator; a
  // document inside the served tree has no reason to write one.
  const ENCODED_SEPARATOR = /%(?:2f|5c)/i;
  // An http(s) address written without its two slashes, which a browser reads as
  // absolute unless the page it sits in shares the scheme.
  const BARE_WEB_SCHEME = /^(https?):(?![/\\]{2})/i;

  /**
   * Whether *href* is a reference inside the served tree: a relative path or fragment.
   * A query alone, and a root-relative path to the application's own routes (`/api`,
   * `/_debug`, `/raw`, however spelled), are not.
   *
   * @param {string | null} href
   */
  function isInside(href) {
    if (!href) {
      return false;
    }
    const cleaned = clean(href);
    if (cleaned === "" || SCHEME.test(cleaned) || OTHER_ORIGIN.test(cleaned)) {
      return false;
    }
    if (cleaned.startsWith("?") || ENCODED_SEPARATOR.test(cleaned)) {
      return false;
    }
    if (cleaned.startsWith("/") || cleaned.startsWith("\\")) {
      // As a browser reads it: an escaped dot is a dot in a dot segment, backslashes
      // are slashes, and dot segments are resolved.
      let path;
      try {
        const dotted = cleaned.replace(/%2e/gi, ".").replaceAll("\\", "/");
        path = new URL(dotted, "http://page.invalid/").pathname;
      } catch {
        return false;
      }
      let decoded = path;
      try {
        decoded = decodeURIComponent(path);
      } catch {
        // A malformed escape is read as written, as the server reads it.
      }
      if (RESERVED.test(decoded)) {
        return false;
      }
    }
    return true;
  }

  /**
   * *href* with a bare `https:` or `http:` given its two slashes, as a browser reads it
   * when the page does not share the scheme.
   *
   * @param {string} href
   * @param {string | null} base
   */
  function spelledOut(href, base) {
    const bare = BARE_WEB_SCHEME.exec(href);
    if (bare === null) {
      return href;
    }
    const scheme = bare[1].toLowerCase();
    if (base !== null && new URL(base).protocol === `${scheme}:`) {
      return href;
    }
    return `${scheme}://${href.slice(bare[0].length).replace(/^[/\\]+/, "")}`;
  }

  /**
   * *href* as an absolute http(s) address, or null. Against *base* when there is one;
   * without one only an absolute reference qualifies.
   *
   * @param {string | null} href
   * @param {string | null} base
   * @returns {string | null}
   */
  function outsideLink(href, base) {
    if (!href) {
      return null;
    }
    const cleaned = spelledOut(clean(href), base);
    if (base === null && !SCHEME.test(cleaned) && !OTHER_ORIGIN.test(cleaned)) {
      return null;
    }
    try {
      const url = new URL(cleaned, base ?? "https://invalid.example/");
      return url.protocol === "https:" || url.protocol === "http:" ? url.href : null;
    } catch {
      return null;
    }
  }

  /**
   * What a link keeps: its address and whether it leaves the page, or null.
   *
   * @param {string | null} href
   * @param {string | null} base
   * @returns {{href: string, leaves: boolean} | null}
   */
  function linkHref(href, base) {
    if (base === null && isInside(href)) {
      const cleaned = clean(href ?? "");
      return { href: cleaned.startsWith("#") ? fragmentLink(cleaned) : cleaned, leaves: false };
    }
    const outside = outsideLink(href, base);
    return outside === null ? null : { href: outside, leaves: true };
  }

  /**
   * The attributes an allowed tag keeps, in a fixed order, each value checked.
   *
   * @param {string} tag
   * @param {(name: string) => string | null} read
   * @param {string | null} base
   * @returns {Array<[string, string]>}
   */
  function allowedAttributes(tag, read, base) {
    /** @type {Array<[string, string]>} */
    const kept = [];
    if (tag === "a") {
      const link = linkHref(read("href"), base);
      if (link !== null) {
        kept.push(["href", link.href]);
        if (link.leaves) {
          kept.push(["target", "_blank"], ["rel", "noopener noreferrer"]);
        }
      }
    } else if (tag === "img") {
      kept.push(["src", clean(read("src") ?? "")]);
      const alt = read("alt");
      if (alt) {
        kept.push(["alt", alt]);
      }
    } else if (tag === "ol") {
      const start = read("start") ?? "";
      if (/^[0-9]{1,6}$/.test(start)) {
        kept.push(["start", start]);
      }
    } else if (tag === "td" || tag === "th") {
      for (const name of ["colspan", "rowspan"]) {
        const value = read(name) ?? "";
        if (/^[1-9][0-9]?$/.test(value)) {
          kept.push([name, value]);
        }
      }
      const align = (read("align") ?? "").toLowerCase();
      if (align === "left" || align === "center" || align === "right") {
        kept.push(["align", align]);
      }
    } else if (tag === "details" && read("open") !== null) {
      kept.push(["open", ""]);
    }
    return kept;
  }

  /**
   * Whether an image stays an image: only one inside the served tree, and only then.
   *
   * @param {string | null} src
   * @param {string | null} base
   */
  function keepsImage(src, base) {
    return base === null && isInside(src);
  }

  /**
   * What an image becomes when it is not kept: a link's href, if any, and its text.
   *
   * @param {string | null} src
   * @param {string | null} alt
   * @param {string | null} base
   */
  function imageLink(src, alt, base) {
    return { href: outsideLink(src, base), text: (alt ?? "").trim() || "image" };
  }

  /**
   * @param {Pick<Document, "createElement">} doc
   * @param {string} tag
   * @param {Array<[string, string]>} attributes
   */
  function element(doc, tag, attributes) {
    const node = doc.createElement(tag);
    for (const [name, value] of attributes) {
      node.setAttribute(name, value);
    }
    return node;
  }

  /**
   * Rebuild parsed nodes from the allowlist alone. Nothing of *nodes* is returned. In a
   * document (a null *base*) each heading gets its anchor, in document order, from the
   * text it shows.
   *
   * @param {ArrayLike<Node>} nodes A template's, where nothing has loaded.
   * @param {Pick<Document, "createElement" | "createTextNode">} doc
   * @param {string | null} base A pull request's github.com page, or null for a
   *   document inside the served tree.
   * @returns {Node[]}
   */
  function sanitizeNodes(nodes, doc, base) {
    /** @type {Heading[]} */
    const headings = [];
    const out = rebuild(nodes, doc, base, headings, []);
    const anchor = createAnchors();
    for (const heading of headings) {
      heading.element.setAttribute("id", anchor(heading.text.join("")));
    }
    return out;
  }

  /** @typedef {{element: Element, text: string[]}} Heading */

  /**
   * @param {ArrayLike<Node>} nodes
   * @param {Pick<Document, "createElement" | "createTextNode">} doc
   * @param {string | null} base
   * @param {Heading[]} headings Every heading so far, in document order.
   * @param {Heading[]} open The headings the text written now belongs to.
   * @returns {Node[]}
   */
  function rebuild(nodes, doc, base, headings, open) {
    /** @type {Node[]} */
    const out = [];
    /** @param {string} text */
    const shown = (text) => {
      for (const heading of open) {
        heading.text.push(text);
      }
    };
    for (const node of Array.from(nodes)) {
      if (node.nodeType === 3) {
        out.push(doc.createTextNode(node.nodeValue ?? ""));
        shown(node.nodeValue ?? "");
        continue;
      }
      if (node.nodeType !== 1) {
        continue;
      }
      const source = /** @type {Element} */ (node);
      const tag = source.tagName.toLowerCase();
      if (DROPPED_WITH_CONTENT.includes(tag)) {
        continue;
      }
      /** @param {string} name */
      const read = (name) => source.getAttribute(name);
      if (tag === "img") {
        if (keepsImage(read("src"), base)) {
          out.push(element(doc, "img", allowedAttributes("img", read, base)));
          continue;
        }
        const image = imageLink(read("src"), read("alt"), base);
        const link = element(
          doc,
          image.href === null ? "span" : "a",
          image.href === null ? [] : allowedAttributes("a", () => image.href, base),
        );
        link.append(doc.createTextNode(image.text));
        shown(image.text);
        out.push(link);
        continue;
      }
      if (!ALLOWED_TAGS.includes(tag)) {
        out.push(...rebuild(source.childNodes, doc, base, headings, open));
        continue;
      }
      const clean = element(doc, tag, allowedAttributes(tag, read, base));
      let inside = open;
      if (base === null && HEADINGS.includes(tag)) {
        const heading = { element: clean, text: [] };
        headings.push(heading);
        inside = [...open, heading];
      }
      clean.append(...rebuild(source.childNodes, doc, base, headings, inside));
      out.push(clean);
    }
    return out;
  }

  /**
   * Parse *html* into an inert template and rebuild it from the allowlist, in a detached
   * document. Browser only.
   *
   * @param {string} html
   * @param {string | null} base
   * @returns {Node[]}
   */
  function sanitizeHtml(html, base) {
    const template = document.createElement("template");
    template.innerHTML = html;
    // Built in a document of their own: an image there loads nothing until the page
    // adopts it, after its caller has resolved or dropped its address.
    const scratch = document.implementation.createHTMLDocument("");
    return sanitizeNodes(template.content.childNodes, scratch, base);
  }

  window.MetabrowserInertHtml = Object.freeze({
    ALLOWED_ATTRIBUTES,
    ANCHOR_PREFIX,
    ALLOWED_TAGS,
    DROPPED_WITH_CONTENT,
    allowedAttributes,
    fragmentLink,
    headingSlug,
    imageLink,
    isInside,
    keepsImage,
    linkHref,
    outsideLink,
    sanitizeHtml,
    sanitizeNodes,
  });
})();
