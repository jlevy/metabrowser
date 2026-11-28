// The shared chooser for sources which contain more than one table.

/** @typedef {{label: string, estimate: string, note?: string, href: string, open: () => unknown}} CatalogRow */
/** @typedef {{title: string, group?: string, rows: ReadonlyArray<CatalogRow>}} CatalogGroup */

/**
 * Preserve ordinary link behavior for modified clicks and the context menu.
 * @param {CatalogRow} row
 * @returns {HTMLAnchorElement}
 */
function catalogLink(row) {
  const link = document.createElement("a");
  link.setAttribute("href", row.href);
  link.textContent = row.label;
  link.addEventListener("click", (event) => {
    if (event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) {
      return;
    }
    event.preventDefault();
    void Promise.resolve(row.open()).catch(() => {});
  });
  return link;
}

/**
 * Draw linked table names, their notes, and right-aligned counts in the shared catalog.
 * @param {HTMLElement} container
 * @param {ReadonlyArray<CatalogGroup>} groups
 */
export function renderTableCatalog(container, groups) {
  const catalog = document.createElement("div");
  catalog.className = "table-catalog";
  for (const group of groups) {
    const section = document.createElement("section");
    if (group.group) {
      section.dataset.group = group.group;
    }
    const heading = document.createElement("h2");
    heading.className = "data-label table-catalog-heading";
    heading.textContent = group.title;
    const table = document.createElement("table");
    table.className = "data-grid table-catalog-list";
    table.setAttribute("aria-label", group.title);
    const body = document.createElement("tbody");
    for (const row of group.rows) {
      const line = document.createElement("tr");
      const name = document.createElement("th");
      name.className = "table-catalog-name";
      name.setAttribute("scope", "row");
      name.append(catalogLink(row));
      if (row.note) {
        const note = document.createElement("span");
        note.className = "table-catalog-note";
        note.textContent = row.note;
        name.append(note);
      }
      const estimate = document.createElement("td");
      estimate.className = "data-num table-catalog-estimate";
      estimate.textContent = row.estimate;
      line.append(name, estimate);
      body.append(line);
    }
    table.append(body);
    section.append(heading, table);
    catalog.append(section);
  }
  container.replaceChildren(catalog);
}
