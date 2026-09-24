// Reduce rendered Markdown from an untrusted source to a small allowlist of plain markup,
// in the browser. The same rules as src/metabrowser/inert_html.py, which applies them
// first on the server; tests/test_inert_html.py proves the two allowlists are the same.
//
// The page never inserts parsed nodes. `sanitizeHtml` parses into a <template>, whose
// content is inert -- nothing in it loads or runs -- and `sanitizeNodes` builds new nodes
// from the allowlist alone: new elements for allowed tags with only their checked
// attributes, new text, images kept only inside the served tree and otherwise turned
// into links, other tags unwrapped, and the dropped ones gone with their content. No
// class, id, name, data, style, or event attribute survives, nor any SVG, MathML,
// media, stylesheet, frame, or form.
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
  // The attributes each tag may keep; every value is checked by allowedAttributes.
  const ALLOWED_ATTRIBUTES = Object.freeze({
    a: Object.freeze(["href", "target", "rel"]),
    img: Object.freeze(["src", "alt"]),
    ol: Object.freeze(["start"]),
    td: Object.freeze(["colspan", "rowspan", "align"]),
    th: Object.freeze(["colspan", "rowspan", "align"]),
    details: Object.freeze(["open"]),
  });

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

  /**
   * Whether *href* is a reference inside the served tree: a relative path or fragment.
   *
   * @param {string | null} href
   */
  function isInside(href) {
    if (!href) {
      return false;
    }
    const cleaned = clean(href);
    return cleaned !== "" && !SCHEME.test(cleaned) && !OTHER_ORIGIN.test(cleaned);
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
    const cleaned = clean(href);
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
      return { href: clean(href ?? ""), leaves: false };
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
   * Rebuild parsed nodes from the allowlist alone. Nothing of *nodes* is returned.
   *
   * @param {ArrayLike<Node>} nodes A template's, where nothing has loaded.
   * @param {Pick<Document, "createElement" | "createTextNode">} doc
   * @param {string | null} base A pull request's github.com page, or null for a
   *   document inside the served tree.
   * @returns {Node[]}
   */
  function sanitizeNodes(nodes, doc, base) {
    /** @type {Node[]} */
    const out = [];
    for (const node of Array.from(nodes)) {
      if (node.nodeType === 3) {
        out.push(doc.createTextNode(node.nodeValue ?? ""));
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
        out.push(link);
        continue;
      }
      const children = sanitizeNodes(source.childNodes, doc, base);
      if (!ALLOWED_TAGS.includes(tag)) {
        out.push(...children);
        continue;
      }
      const clean = element(doc, tag, allowedAttributes(tag, read, base));
      clean.append(...children);
      out.push(clean);
    }
    return out;
  }

  /**
   * Parse *html* into an inert template and rebuild it from the allowlist. Browser only.
   *
   * @param {string} html
   * @param {string | null} base
   * @returns {Node[]}
   */
  function sanitizeHtml(html, base) {
    const template = document.createElement("template");
    template.innerHTML = html;
    return sanitizeNodes(template.content.childNodes, document, base);
  }

  window.MetabrowserInertHtml = Object.freeze({
    ALLOWED_ATTRIBUTES,
    ALLOWED_TAGS,
    DROPPED_WITH_CONTENT,
    allowedAttributes,
    imageLink,
    isInside,
    keepsImage,
    linkHref,
    outsideLink,
    sanitizeHtml,
    sanitizeNodes,
  });
})();
