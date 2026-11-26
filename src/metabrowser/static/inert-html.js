// Reduce rendered Markdown from an untrusted source to a small allowlist of plain markup,
// in the browser. The same rules as src/metabrowser/inert_html.py, which applies them
// first on the server; tests/test_inert_html.py proves the two allowlists are the same.
//
// The page never inserts parsed nodes. `sanitizeHtml` parses into a <template>, whose
// content is inert -- nothing in it loads or runs -- and `sanitizeNodes` builds new nodes
// from the allowlist alone: new elements for allowed tags with only their checked
// attributes, new text, images kept only inside the served tree and otherwise turned
// into a fallback, other tags unwrapped, and the dropped ones gone with their content. No
// class, name, data, style, or event attribute survives, nor any SVG, MathML, media,
// stylesheet, frame, form, or input but a disabled checkbox in the shape of a task
// list's box, wherever the document writes one, and no id the document wrote: in a
// document inside the served tree each heading gets the anchor github.com would give it,
// `user-content-` and the slug of its text, and a `#name` link becomes
// `#user-content-name`. The server makes the anchors; a heading keeps the one it
// arrives with, which can only name that namespace, so the page and the server agree
// whatever Unicode version each slugs by.
//
// `kpressProse` then sets those nodes in KPress's prose element, with the classes KPress's
// stylesheets hang a table and a code block on. The classes are this module's, chosen by
// element, so a document still names none.
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
  const HEADINGS = Object.freeze(["h1", "h2", "h3", "h4", "h5", "h6"]);
  // The align keywords each tag keeps, lowercased, and the sizes it keeps, as
  // inert_html.py lists them: the layout attributes github.com keeps, each a keyword or
  // a number.
  const TEXT_ALIGN = Object.freeze(["left", "center", "right", "justify"]);
  /** @type {Readonly<Record<string, readonly string[]>>} */
  const ALIGN_VALUES = Object.freeze({
    p: TEXT_ALIGN,
    div: TEXT_ALIGN,
    ...Object.fromEntries(HEADINGS.map((tag) => [tag, TEXT_ALIGN])),
    img: Object.freeze(["left", "right", "top", "middle", "center", "bottom", "baseline"]),
    table: Object.freeze(["left", "center", "right"]),
    ...Object.fromEntries(
      ["thead", "tbody", "tfoot", "tr", "td", "th"].map((tag) => [tag, TEXT_ALIGN]),
    ),
  });
  /** @type {Readonly<Record<string, readonly string[]>>} */
  const DIMENSIONS = Object.freeze({
    img: Object.freeze(["width", "height"]),
    table: Object.freeze(["width"]),
    td: Object.freeze(["width", "height"]),
    th: Object.freeze(["width", "height"]),
  });
  // A number, with an optional fraction, then `%` or the `px` a README often writes; five
  // digits, for the reason inert_html.py gives beside its _DIMENSION.
  const DIMENSION = /^[0-9]{1,5}(?:\.[0-9]{1,3})?(?:%|px)?$/i;
  // What an image the page does not load becomes, and the policy one from the web is
  // fetched under, as inert_html.py has them.
  const IMAGE_FALLBACK_CLASS = "mb-image-fallback";
  const IMAGE_REFERRER_POLICY = "no-referrer";
  // The attributes each tag may keep; every value is checked by allowedAttributes,
  // except a heading's id, which is always sanitizeNodes' own anchor, an image's loading,
  // which is always lazy, its referrerpolicy, which is always no-referrer, and a span's,
  // which only the image fallback's own shape keeps. An input is kept only in the shape
  // of a task list's box, which CHECKBOX_ATTRIBUTES writes, wherever the document writes
  // a checkbox.
  const ALLOWED_ATTRIBUTES = Object.freeze({
    a: Object.freeze(["href", "target", "rel"]),
    img: Object.freeze(["loading", "referrerpolicy", "src", "alt", "align", "width", "height"]),
    input: Object.freeze(["type", "disabled", "checked"]),
    span: Object.freeze(["class", "data-tip-text"]),
    ol: Object.freeze(["start"]),
    p: Object.freeze(["align"]),
    div: Object.freeze(["align"]),
    table: Object.freeze(["align", "width"]),
    thead: Object.freeze(["align"]),
    tbody: Object.freeze(["align"]),
    tfoot: Object.freeze(["align"]),
    tr: Object.freeze(["align"]),
    td: Object.freeze(["colspan", "rowspan", "align", "width", "height"]),
    th: Object.freeze(["colspan", "rowspan", "align", "width", "height"]),
    details: Object.freeze(["open"]),
    pre: Object.freeze(["lang"]),
    ...Object.fromEntries(HEADINGS.map((tag) => [tag, Object.freeze(["id", "align"])])),
  });
  // The one shape an input keeps, a task list's box, ahead of `checked` when the
  // document's was ticked, as inert_html.py writes it.
  /** @type {ReadonlyArray<readonly [string, string]>} */
  const CHECKBOX_ATTRIBUTES = Object.freeze([
    Object.freeze(/** @type {const} */ (["type", "checkbox"])),
    Object.freeze(/** @type {const} */ (["disabled", ""])),
  ]);
  // The one language a block keeps, a Mermaid diagram's, as inert_html.py keeps it.
  const DIAGRAM_LANGUAGE = "mermaid";

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

  /**
   * GitHub's numbering of repeated slugs (github-slugger): `a`, `a-1`, `a-2`. A heading
   * that arrives with an anchor -- the server made it (inert_html.py), and its Unicode
   * tables, not the browser's, decide the slug -- keeps it the first time it is seen;
   * it can only name the anchor namespace.
   */
  function createAnchors() {
    /** @type {Map<string, number>} */
    const seen = new Map();
    /** @param {string} text @param {string | null} arrived */
    return (text, arrived) => {
      if (arrived?.startsWith(ANCHOR_PREFIX)) {
        const kept = arrived.slice(ANCHOR_PREFIX.length);
        if (!seen.has(kept)) {
          seen.set(kept, 0);
          return arrived;
        }
      }
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
  // An address written in full: its scheme (or none), two slashes in any mix, and a
  // character of the host, as inert_html.py's `_WRITTEN_AUTHORITY`.
  const WRITTEN_AUTHORITY = /^(?:https:)?[/\\]{2}[^/\\?#]/i;
  // The authority a written address names, which is ASCII or no image of the web, as
  // inert_html.py's `_AUTHORITY` says why.
  const AUTHORITY = /^(?:https:)?[/\\]{2}([^/\\?#]*)/i;
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
   * Whether an input's `type` makes it a checkbox, as a browser reads one: ASCII letters
   * in any case, and nothing around them. `toLowerCase` also folds U+212A KELVIN SIGN to
   * `k`, which no browser's match does, as inert_html.py's `_checkbox_type` has it.
   *
   * @param {string | null} kind
   * @returns {boolean}
   */
  function isCheckboxType(kind) {
    const written = kind ?? "";
    return /^[A-Za-z]+$/.test(written) && written.toLowerCase() === "checkbox";
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
      // A constant, so the document has no say in when its images load: a trusted
      // render's images wait until they near the reader, and these wait the same way.
      // Ahead of src, for a browser that reads the two in order.
      kept.push(["loading", "lazy"]);
      const remote = remoteImage(read("src"), base);
      if (remote === null) {
        kept.push(["src", clean(read("src") ?? "")]);
      } else {
        // The address as a browser's URL parser writes it, as a kept link's is.
        kept.push(["referrerpolicy", IMAGE_REFERRER_POLICY], ["src", remote]);
      }
      const alt = read("alt");
      if (alt) {
        kept.push(["alt", alt]);
      }
    } else if (tag === "span") {
      // Only the fallback the server's hardener wrote for an image the page does not
      // load, so its answer hardens to itself, as inert_html.py has it: the class
      // exactly, and an address a browser reads as http(s) for the tooltip.
      if (read("class") === IMAGE_FALLBACK_CLASS) {
        kept.push(["class", IMAGE_FALLBACK_CLASS]);
        const address = outsideLink(read("data-tip-text"), null);
        if (address !== null) {
          kept.push(["data-tip-text", address]);
        }
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
    } else if (tag === "details" && read("open") !== null) {
      kept.push(["open", ""]);
    } else if (tag === "input" && isCheckboxType(read("type"))) {
      for (const [name, value] of CHECKBOX_ATTRIBUTES) {
        kept.push([name, value]);
      }
      if (read("checked") !== null) {
        kept.push(["checked", ""]);
      }
    } else if (
      tag === "pre" &&
      ((read("lang") ?? "").toLowerCase() === DIAGRAM_LANGUAGE ||
        (read("class") ?? "").split(/\s+/).includes("kpress-diagram-source"))
    ) {
      kept.push(["lang", DIAGRAM_LANGUAGE]);
    }
    // A browser matches an align keyword in any case and with nothing around it.
    const align = (read("align") ?? "").toLowerCase();
    if (Object.hasOwn(ALIGN_VALUES, tag) && ALIGN_VALUES[tag].includes(align)) {
      kept.push(["align", align]);
    }
    for (const name of Object.hasOwn(DIMENSIONS, tag) ? DIMENSIONS[tag] : []) {
      const size = read(name) ?? "";
      if (DIMENSION.test(size)) {
        kept.push([name, size]);
      }
    }
    return kept;
  }

  /**
   * The `https` address of an image the page may fetch from the web, or null. Only an
   * address the document writes in full qualifies, so a relative path in a pull request's
   * comment, which `outsideLink` would make absolute against *base*, is not one; nor is
   * `http`, or an address with a user name or password in it, which a browser refuses an
   * image under. Written as `outsideLink` writes it, as inert_html.py's `remote_image`.
   *
   * @param {string | null} src
   * @param {string | null} base
   * @returns {string | null}
   */
  function remoteImage(src, base) {
    if (!src) {
      return null;
    }
    const cleaned = spelledOut(clean(src), base);
    if (
      !WRITTEN_AUTHORITY.test(cleaned) ||
      /[\u0080-\uffff]/.test(AUTHORITY.exec(cleaned)?.[1] ?? "")
    ) {
      return null;
    }
    const outside = outsideLink(src, base);
    if (outside === null || !outside.startsWith("https://")) {
      return null;
    }
    // The URL parser refuses an empty or malformed host or port, as inert_html.py's
    // `_host_parses` does for the same address.
    const url = new URL(outside);
    return url.hostname === "" || url.username !== "" || url.password !== "" ? null : outside;
  }

  /**
   * Whether an image stays an image: one inside the served tree, or one from the web.
   *
   * @param {string | null} src
   * @param {string | null} base
   */
  function keepsImage(src, base) {
    return (base === null && isInside(src)) || remoteImage(src, base) !== null;
  }

  /**
   * Whether the reader has turned off the images of the web, in the shell's settings
   * (`BLOCK_REMOTE_IMAGES`, which the server reads from the reader's preference). It is
   * read at each use, so a page that changes it needs only load again.
   */
  function blocksRemoteImages() {
    return window.METABROWSER_SETTINGS?.BLOCK_REMOTE_IMAGES === true;
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
   * What an image the page does not load becomes: its alt text in a span of the fallback's
   * class, with the address the image would have loaded in its tooltip, and, outside a
   * link, in a link to that address. Inside one, which a badge is, the span is the link's
   * own content: a second link inside it is not valid, and a browser reads it as the
   * first's end.
   *
   * @param {Pick<Document, "createElement" | "createTextNode">} doc
   * @param {string | null} src
   * @param {string | null} alt
   * @param {string | null} base
   * @param {boolean} inLink
   * @returns {{node: Node, text: string}}
   */
  function imageFallback(doc, src, alt, base, inLink) {
    const image = imageLink(src, alt, base);
    /** @type {Array<[string, string]>} */
    const attributes = [["class", IMAGE_FALLBACK_CLASS]];
    if (image.href !== null) {
      attributes.push(["data-tip-text", image.href]);
    }
    const chip = element(doc, "span", attributes);
    chip.append(doc.createTextNode(image.text));
    if (inLink || image.href === null) {
      return { node: chip, text: image.text };
    }
    const link = element(
      doc,
      "a",
      allowedAttributes("a", () => image.href, base),
    );
    link.append(chip);
    return { node: link, text: image.text };
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
   * @param {boolean} [keepPathRelative] Copy the server-issued PR file-link marker.
   * @returns {Node[]}
   */
  function sanitizeNodes(nodes, doc, base, keepPathRelative = false) {
    /** @type {Heading[]} */
    const headings = [];
    const out = rebuild(nodes, doc, base, headings, [], false, keepPathRelative);
    const anchor = createAnchors();
    for (const heading of headings) {
      heading.element.setAttribute("id", anchor(heading.text.join(""), heading.arrived));
    }
    return out;
  }

  /** @typedef {{element: Element, arrived: string | null, text: string[]}} Heading */

  /**
   * @param {ArrayLike<Node>} nodes
   * @param {Pick<Document, "createElement" | "createTextNode">} doc
   * @param {string | null} base
   * @param {Heading[]} headings Every heading so far, in document order.
   * @param {Heading[]} open The headings the text written now belongs to.
   * @param {boolean} inLink Whether the nodes are the content of a link.
   * @param {boolean} keepPathRelative
   * @returns {Node[]}
   */
  function rebuild(nodes, doc, base, headings, open, inLink, keepPathRelative) {
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
        // An image from the web is kept unless the reader has turned them off.
        const fetched = remoteImage(read("src"), base) !== null;
        if (keepsImage(read("src"), base) && !(fetched && blocksRemoteImages())) {
          out.push(element(doc, "img", allowedAttributes("img", read, base)));
          continue;
        }
        const fallback = imageFallback(doc, read("src"), read("alt"), base, inLink);
        shown(fallback.text);
        out.push(fallback.node);
        continue;
      }
      if (tag === "input") {
        // Kept only in the shape of a task list's box, wherever a checkbox is written;
        // any other input is void, so nothing of it is left.
        const kept = allowedAttributes("input", read, base);
        if (kept.length > 0) {
          out.push(element(doc, "input", kept));
        }
        continue;
      }
      if (!ALLOWED_TAGS.includes(tag)) {
        out.push(
          ...rebuild(source.childNodes, doc, base, headings, open, inLink, keepPathRelative),
        );
        continue;
      }
      const clean = element(doc, tag, allowedAttributes(tag, read, base));
      if (
        keepPathRelative &&
        tag === "a" &&
        read("data-metabrowser-path-relative") === "" &&
        clean.hasAttribute("href")
      ) {
        clean.setAttribute("data-metabrowser-path-relative", "");
      }
      let inside = open;
      if (base === null && HEADINGS.includes(tag)) {
        /** @type {Heading} */
        const heading = { element: clean, arrived: read("id"), text: [] };
        headings.push(heading);
        inside = [...open, heading];
      }
      clean.append(
        ...rebuild(
          source.childNodes,
          doc,
          base,
          headings,
          inside,
          inLink || tag === "a",
          keepPathRelative,
        ),
      );
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
   * @param {boolean} [keepPathRelative]
   * @returns {Node[]}
   */
  function sanitizeHtml(html, base, keepPathRelative = false) {
    const template = document.createElement("template");
    template.innerHTML = html;
    // Built in a document of their own: an image there loads nothing until the page
    // adopts it, after its caller has resolved or dropped its address.
    const scratch = document.implementation.createHTMLDocument("");
    return sanitizeNodes(template.content.childNodes, scratch, base, keepPathRelative);
  }

  /**
   * KPress's own wrappers around a render's blocks, which arrive as two bare `<div>`s once
   * the allowlist has taken their classes. Dropped, so the blocks are the prose element's
   * children, as KPress's stylesheets and the host's first-heading rule expect. Exactly
   * these two: a `<div>` beneath them is a table's or the document's own, and so is one
   * with an attribute, which only a document's `align` can give a `<div>`.
   *
   * @param {Node[]} nodes
   * @returns {Node[]}
   */
  function withoutRenderWrappers(nodes) {
    let blocks = nodes;
    for (let depth = 0; depth < 2; depth += 1) {
      const present = blocks.filter((node) => node.nodeType !== 3 || node.textContent?.trim());
      const only = /** @type {Element | undefined} */ (
        present.length === 1 ? present[0] : undefined
      );
      if (only?.tagName !== "DIV" || only.attributes.length > 0) {
        break;
      }
      blocks = Array.from(only.childNodes);
    }
    return blocks;
  }

  /**
   * Sanitized *nodes* in a `.kpress-prose` element, so KPress's stylesheets set them as they
   * set a Markdown file. KPress hangs a code block's frame and a table's type on classes the
   * allowlist removed, so they are put back here by element: `pre`, `table`, and the `<div>`
   * KPress keeps around a table. The caller provides the article around it.
   *
   * @param {Node[]} nodes What `sanitizeHtml` returned.
   * @param {Document} doc
   * @returns {HTMLElement}
   */
  function kpressProse(nodes, doc) {
    const prose = doc.createElement("div");
    prose.className = "kpress-prose";
    prose.append(...withoutRenderWrappers(nodes));
    for (const pre of prose.querySelectorAll("pre")) {
      pre.className = "kpress-code";
    }
    for (const table of prose.querySelectorAll("table")) {
      table.className = "kpress-table";
      const parent = table.parentElement;
      if (parent && parent !== prose && parent.tagName === "DIV") {
        parent.className = "kpress-table-wrap";
      }
    }
    return prose;
  }

  window.MetabrowserInertHtml = Object.freeze({
    ALIGN_VALUES,
    ALLOWED_ATTRIBUTES,
    ANCHOR_PREFIX,
    ALLOWED_TAGS,
    CHECKBOX_ATTRIBUTES,
    DIMENSIONS,
    DROPPED_WITH_CONTENT,
    IMAGE_FALLBACK_CLASS,
    IMAGE_REFERRER_POLICY,
    allowedAttributes,
    blocksRemoteImages,
    fragmentLink,
    headingSlug,
    imageLink,
    isInside,
    keepsImage,
    kpressProse,
    linkHref,
    outsideLink,
    remoteImage,
    sanitizeHtml,
    sanitizeNodes,
  });
})();
