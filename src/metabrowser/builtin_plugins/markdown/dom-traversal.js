/**
 * Matching descendants of one rendered Markdown container, in document order,
 * at most `limit` of them.
 *
 * Native `querySelectorAll` walks the subtree once per call and returns only
 * matches, so every lookup is independent: link admission, nested
 * transclusions, and later fragment navigation cannot exhaust one another.
 * What follows a lookup is bounded by the caller's enhancement budget, not by
 * a count of visited elements.
 *
 * @param {ParentNode} container
 * @param {string} selector
 * @param {number=} limit
 * @returns {Element[]}
 */
export function matchingDescendants(container, selector, limit = Number.POSITIVE_INFINITY) {
  const matches = container.querySelectorAll(selector);
  const count = Math.min(matches.length, limit);
  /** @type {Element[]} */
  const elements = [];
  for (let index = 0; index < count; index += 1) {
    elements.push(matches[index]);
  }
  return elements;
}

/**
 * The first descendant whose `id` equals `id` exactly, or null.
 *
 * An attribute selector keeps the lookup inside `container` (a document may
 * repeat an id outside the rendered Markdown) and needs only quoting, not
 * identifier escaping, so any authored heading or block id is found.
 *
 * @param {ParentNode} container
 * @param {string} id
 * @returns {Element | null}
 */
export function findElementById(container, id) {
  if (!id) {
    return null;
  }
  return container.querySelector(`[id="${quotedAttributeValue(id)}"]`);
}

/** @param {string} value */
function quotedAttributeValue(value) {
  return value
    .replace(/["\\]/g, "\\$&")
    .replace(/[\n\r\f]/g, (character) => `\\${character.charCodeAt(0).toString(16)} `)
    .replace(/\0/g, "\\fffd ");
}
