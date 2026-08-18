export const PLACEMENT_ORDER = Object.freeze({ summary: 0, content: 1, supplemental: 2 });
const PRESENTATIONS = new Set(["surface", "document"]);
/** @typedef {{message: string, retryable: boolean}} PanelErrorClassification */
/** @typedef {{label: string, placement: "summary" | "content" | "supplemental", presentation: "surface" | "document", resolve: (...args: Array<any>) => any, mount: (...args: Array<any>) => any, required?: boolean, printable?: boolean, collapsible?: boolean, defaultExpanded?: boolean, classifyError?: (error: unknown) => PanelErrorClassification}} PanelSpec */
/** @typedef {Readonly<PanelSpec & {id: string}>} PanelDescriptor */

/** @param {string} id */
export function validatePanelId(id) {
  if (!/^[a-z][a-z0-9-]*\.[a-z][a-z0-9-]*$/.test(id)) {
    throw new TypeError("panel id must be plugin-qualified, for example example.license");
  }
}

/** @param {PanelSpec} spec */
export function validatePanelSpec(spec) {
  if (!spec || typeof spec !== "object") {
    throw new TypeError("panel spec must be an object");
  }
  if (typeof spec.label !== "string" || !spec.label.trim()) {
    throw new TypeError("panel label must be a non-empty string");
  }
  if (!(spec.placement in PLACEMENT_ORDER)) {
    throw new TypeError("panel placement must be summary, content, or supplemental");
  }
  if (!PRESENTATIONS.has(spec.presentation)) {
    throw new TypeError("panel presentation must be surface or document");
  }
  if (typeof spec.resolve !== "function" || typeof spec.mount !== "function") {
    throw new TypeError("panel spec requires resolve and mount functions");
  }
  if (spec.required !== undefined && typeof spec.required !== "boolean") {
    throw new TypeError("panel required must be boolean");
  }
  if (spec.printable !== undefined && typeof spec.printable !== "boolean") {
    throw new TypeError("panel printable must be boolean");
  }
  if (spec.collapsible !== undefined && typeof spec.collapsible !== "boolean") {
    throw new TypeError("panel collapsible must be boolean");
  }
  if (spec.defaultExpanded !== undefined && typeof spec.defaultExpanded !== "boolean") {
    throw new TypeError("panel defaultExpanded must be boolean");
  }
  if (spec.classifyError !== undefined && typeof spec.classifyError !== "function") {
    throw new TypeError("panel classifyError must be a function");
  }
}

/** @param {PanelDescriptor} left @param {PanelDescriptor} right */
export function comparePanels(left, right) {
  return (
    PLACEMENT_ORDER[left.placement] - PLACEMENT_ORDER[right.placement] ||
    left.id.localeCompare(right.id)
  );
}

/** @param {MetabrowserPublicSdk} _mb */
export function createFolderOverviewRegistry(_mb) {
  const generic = window.MetabrowserContributionRegistry.createContributionRegistry(
    /** @type {{validate: (id: string, spec: PanelSpec) => void, compare: (left: PanelDescriptor, right: PanelDescriptor) => number}} */ ({
      validate(id, spec) {
        validatePanelId(id);
        validatePanelSpec(spec);
      },
      compare: comparePanels,
    }),
  );
  return Object.freeze({
    registerPanel: generic.register,
    listPanels: generic.list,
  });
}
