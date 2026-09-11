/**
 * Yield matching descendants without materializing an unbounded NodeList.
 *
 * The querySelectorAll branch exists for browserless contract shims only. Real DOM
 * documents expose createTreeWalker, so production stops traversing as soon as the
 * caller stops consuming the generator.
 *
 * @param {HTMLElement} container
 * @param {string} selector
 * @param {ReturnType<typeof createMarkdownDomTraversalBudget>=} budget
 */
export function* matchingDescendants(
  container,
  selector,
  budget = createMarkdownDomTraversalBudget(),
) {
  if (!DOM_BUDGETS.has(budget)) {
    throw new TypeError("Markdown DOM traversal requires a module-created budget");
  }
  const document = container.ownerDocument || globalThis.document;
  if (document && typeof document.createTreeWalker === "function") {
    const walker = document.createTreeWalker(container, 1);
    let current = walker.nextNode();
    while (current) {
      if (!claimVisit(budget)) {
        return;
      }
      const element = /** @type {Element} */ (current);
      if (element.matches(selector)) {
        yield element;
      }
      current = walker.nextNode();
    }
    return;
  }
  for (const element of container.querySelectorAll(selector)) {
    if (!claimVisit(budget)) {
      return;
    }
    yield element;
  }
}

/** @param {ReturnType<typeof createMarkdownDomTraversalBudget>} budget */
function claimVisit(budget) {
  if (budget.state.visits >= MAX_MARKDOWN_DOM_VISITS) {
    return false;
  }
  budget.state.visits += 1;
  return true;
}
const MAX_MARKDOWN_DOM_VISITS = 16_384;
const DOM_BUDGETS = new WeakSet();

/** Create the hard root-scoped ceiling for synchronous Markdown DOM inspection. */
export function createMarkdownDomTraversalBudget() {
  const budget = Object.freeze({ state: { visits: 0 } });
  DOM_BUDGETS.add(budget);
  return budget;
}
