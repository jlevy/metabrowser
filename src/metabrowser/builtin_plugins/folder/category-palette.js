// The color a distribution segment is painted, from the key it carries.
//
// This used to be a scarcity problem. Twelve hand-tuned slots were handed out
// by hashing a key to a starting slot and probing forward for a free one, per
// folder, with a reservation table reconciled whenever a panel mounted or
// unmounted. A family's color therefore depended on which other families
// happened to be visible beside it, so the same folder could repaint on an
// expand and the same language could be two colors in two folders.
//
// The registry now declares a hue per family, the server resolves each one
// against both themes, and this module is the lookup between them. No session,
// no reservation, no allocation, and the same key is the same color anywhere.
//
// Why the colors arrive finished rather than as hues composed in CSS: sRGB
// cannot hold the palette's target chroma at every hue, and a browser handed an
// out-of-gamut oklch() clips it — which moves hue, measured at up to nine
// degrees, more than the separation the palette is built on. The pullback
// happens once, in color_oklch.py. See file_type_filters.serialize_distribution_colors.

export const OTHER_KEY = "";

/** The class a segment carries when it has no color of its own. */
export const OTHER_CLASS = "mb-distribution-other";

/** The class that selects between the two theme colors below. */
export const MARK_CLASS = "mb-distribution-mark";

/** Where a segment's color on each theme is written. */
export const LIGHT_PROPERTY = "--mb-distribution-color-light";
export const DARK_PROPERTY = "--mb-distribution-color-dark";

/**
 * @param {string} key
 * @param {number} count
 */
function hashIndex(key, count) {
  let hash = 2166136261;
  for (let index = 0; index < key.length; index += 1) {
    hash ^= key.charCodeAt(index);
    hash = Math.imul(hash, 16777619);
  }
  // Golden-ratio steps rather than a plain modulus, so consecutive hashes land
  // far apart in the list and the handful of extensions in one folder rarely
  // draw the same color.
  return Math.floor((((hash >>> 0) * 0.6180339887) % 1) * count);
}

/**
 * @param {ReadonlyArray<{key: string, light: string, dark: string}>} colors
 */
export function createCategoryPalette(colors) {
  const byKey = new Map(colors.map((entry) => [entry.key, entry]));

  /** @param {string} key */
  function colorFor(key) {
    if (key === OTHER_KEY || colors.length === 0) {
      return null;
    }
    const declared = byKey.get(key);
    if (declared) {
      return declared;
    }
    // A key the registry does not know: an extension inside Other types, which
    // is unfamilied by definition. Distinguishing these from each other is the
    // whole job — they sit together under one parent — so borrowing a declared
    // color is enough, and no allocator has to exist for them.
    return colors[hashIndex(key, colors.length)];
  }

  return Object.freeze({
    colorFor,
    /**
     * The classes for a segment: one that selects the theme, or the neutral
     * for a segment with no color behind it.
     * @param {string} key
     */
    classFor(key) {
      return colorFor(key) === null ? OTHER_CLASS : MARK_CLASS;
    },
    /**
     * The same answer as an inline style fragment, for callers that build
     * markup as a string rather than as elements.
     * @param {string} key
     */
    styleFor(key) {
      const color = colorFor(key);
      return color === null
        ? ""
        : `${LIGHT_PROPERTY}:${color.light};${DARK_PROPERTY}:${color.dark};`;
    },
    /**
     * Paint an element. One call rather than a class and two properties, so a
     * caller cannot set some of them and forget the rest.
     * @param {HTMLElement} element
     * @param {string} key
     */
    paint(element, key) {
      const color = colorFor(key);
      element.classList?.toggle(OTHER_CLASS, color === null);
      element.classList?.toggle(MARK_CLASS, color !== null);
      if (color === null) {
        element.style?.removeProperty(LIGHT_PROPERTY);
        element.style?.removeProperty(DARK_PROPERTY);
      } else {
        element.style?.setProperty(LIGHT_PROPERTY, color.light);
        element.style?.setProperty(DARK_PROPERTY, color.dark);
      }
    },
  });
}
