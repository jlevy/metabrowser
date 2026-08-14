/**
 * Validated browser runtime for the server-owned semantic file type catalog.
 */

((global) => {
  if (global.MetabrowserFileTypeTaxonomy) {
    return;
  }

  const FAMILY_KEY_PREFIX = "family:";
  const NO_EXTENSION_KEY = "(none)";
  const REMAINING_KEY = "";
  const VALID_ID = /^[a-z][a-z0-9-]*$/;

  /** @typedef {"docs" | "code" | "data"} FileTypeCategoryId */
  /** @typedef {FileTypeCategoryId | "other"} ClassifiedFileTypeCategoryId */
  /** @typedef {Readonly<{id: FileTypeCategoryId, label: string, extraValues: ReadonlyArray<string>}>} FileTypeCategory */
  /** @typedef {Readonly<{id: string, label: string, category: FileTypeCategoryId, extensions: ReadonlyArray<string>}>} FileTypeFamily */
  /** @typedef {Readonly<{family: FileTypeFamily, canonicalExtension: string}>} FileTypeFamilyMatch */

  /** @param {unknown} value @param {string} label */
  function objectValue(value, label) {
    if (!value || typeof value !== "object" || Array.isArray(value)) {
      throw new TypeError(`${label} must be an object`);
    }
    return /** @type {Record<string, unknown>} */ (value);
  }

  /** @param {unknown} value @param {string} label */
  function stringValue(value, label) {
    if (typeof value !== "string" || !value.trim()) {
      throw new TypeError(`${label} must be a non-empty string`);
    }
    return value;
  }

  /** @param {unknown} value @param {string} label */
  function stringArray(value, label) {
    if (!Array.isArray(value)) {
      throw new TypeError(`${label} must be an array`);
    }
    return Object.freeze(value.map((item) => stringValue(item, label)));
  }

  /** @param {unknown} extension */
  function normalizeExtension(extension) {
    if (typeof extension !== "string") {
      return REMAINING_KEY;
    }
    const normalized = extension.trim().toLowerCase();
    if (!normalized || normalized === REMAINING_KEY) {
      return REMAINING_KEY;
    }
    if (normalized === NO_EXTENSION_KEY) {
      return NO_EXTENSION_KEY;
    }
    return normalized.startsWith(".") ? normalized : `.${normalized}`;
  }

  /** @param {string} extension @param {string} suffix */
  function extensionMatches(extension, suffix) {
    return extension === suffix || extension.endsWith(suffix);
  }

  /** @param {unknown} rawTaxonomy */
  function createRuntime(rawTaxonomy) {
    const raw = objectValue(rawTaxonomy, "FILE_TYPE_TAXONOMY");
    if (!Array.isArray(raw.categories) || !Array.isArray(raw.families)) {
      throw new TypeError("FILE_TYPE_TAXONOMY must contain category and family arrays");
    }

    /** @type {Set<string>} */
    const categoryIds = new Set();
    /** @type {Map<string, FileTypeCategoryId>} */
    const categoryFilenames = new Map();
    /** @type {Array<Readonly<{suffix: string, category: FileTypeCategoryId}>>} */
    const categorySuffixes = [];
    /** @type {Array<FileTypeCategory>} */
    const categories = raw.categories.map((candidate) => {
      const value = objectValue(candidate, "file type category");
      const id = stringValue(value.id, "file type category id");
      if (!VALID_ID.test(id) || (id !== "docs" && id !== "code" && id !== "data")) {
        throw new TypeError(`invalid file type category id: ${id}`);
      }
      if (categoryIds.has(id)) {
        throw new TypeError(`duplicate file type category id: ${id}`);
      }
      categoryIds.add(id);
      const categoryId = /** @type {FileTypeCategoryId} */ (id);
      const extras = stringArray(value.extra_values, `extra values for ${id}`);
      for (const extra of extras) {
        if (extra === "." || extra !== extra.trim().toLowerCase()) {
          throw new TypeError(`file type category values must be normalized: ${extra}`);
        }
        if (
          categoryFilenames.has(extra) ||
          categorySuffixes.some((item) => item.suffix === extra)
        ) {
          throw new TypeError(`duplicate file type category value: ${extra}`);
        }
        if (extra.startsWith(".")) {
          categorySuffixes.push(Object.freeze({ suffix: extra, category: categoryId }));
        } else {
          categoryFilenames.set(extra, categoryId);
        }
      }
      return Object.freeze({
        id: categoryId,
        label: stringValue(value.label, `label for ${id}`),
        extraValues: extras,
      });
    });

    /** @type {Set<string>} */
    const familyIds = new Set();
    /** @type {Set<string>} */
    const familyExtensions = new Set();
    /** @type {Array<FileTypeFamily>} */
    const families = raw.families.map((candidate) => {
      const value = objectValue(candidate, "file type family");
      const id = stringValue(value.id, "file type family id");
      if (!VALID_ID.test(id)) {
        throw new TypeError(`invalid file type family id: ${id}`);
      }
      if (familyIds.has(id)) {
        throw new TypeError(`duplicate file type family id: ${id}`);
      }
      familyIds.add(id);
      const category = stringValue(value.category, `category for ${id}`);
      if (!categoryIds.has(category)) {
        throw new TypeError(`unknown category ${category} for file type family ${id}`);
      }
      const extensions = stringArray(value.extensions, `extensions for ${id}`);
      if (extensions.length === 0) {
        throw new TypeError(`file type family has no extensions: ${id}`);
      }
      for (const extension of extensions) {
        if (
          normalizeExtension(extension) !== extension ||
          !extension.startsWith(".") ||
          extension === "."
        ) {
          throw new TypeError(`file type family extensions must be normalized: ${extension}`);
        }
        if (familyExtensions.has(extension)) {
          throw new TypeError(`duplicate file type family extension: ${extension}`);
        }
        if (
          categoryFilenames.has(extension) ||
          categorySuffixes.some((item) => item.suffix === extension)
        ) {
          throw new TypeError(
            `file type value ${extension} is both a family member and category-only value`,
          );
        }
        familyExtensions.add(extension);
      }
      return Object.freeze({
        id,
        label: stringValue(value.label, `label for ${id}`),
        category: /** @type {FileTypeCategoryId} */ (category),
        extensions,
      });
    });

    const frozenCategories = Object.freeze(categories);
    const frozenFamilies = Object.freeze(families);
    const familySuffixes = Object.freeze(
      families
        .flatMap((family) => family.extensions.map((suffix) => Object.freeze({ suffix, family })))
        .sort(
          (left, right) =>
            right.suffix.length - left.suffix.length ||
            left.suffix.localeCompare(right.suffix) ||
            left.family.id.localeCompare(right.family.id),
        ),
    );
    categorySuffixes.sort(
      (left, right) =>
        right.suffix.length - left.suffix.length ||
        left.suffix.localeCompare(right.suffix) ||
        left.category.localeCompare(right.category),
    );

    /** @param {unknown} extension @returns {FileTypeFamilyMatch | null} */
    function matchExtension(extension) {
      const normalized = normalizeExtension(extension);
      if (!normalized.startsWith(".")) {
        return null;
      }
      for (const candidate of familySuffixes) {
        if (extensionMatches(normalized, candidate.suffix)) {
          return Object.freeze({
            family: candidate.family,
            canonicalExtension: candidate.suffix,
          });
        }
      }
      return null;
    }

    /** @param {unknown} extension */
    function canonicalExtension(extension) {
      const normalized = normalizeExtension(extension);
      return matchExtension(normalized)?.canonicalExtension ?? normalized;
    }

    /** @param {unknown} name @param {unknown} extension @returns {ClassifiedFileTypeCategoryId} */
    function categoryForFile(name, extension) {
      const match = matchExtension(extension);
      if (match) {
        return match.family.category;
      }
      const normalized = normalizeExtension(extension);
      if (normalized.startsWith(".")) {
        for (const candidate of categorySuffixes) {
          if (extensionMatches(normalized, candidate.suffix)) {
            return candidate.category;
          }
        }
      }
      const basename =
        typeof name === "string"
          ? (name.replace(/\\/g, "/").split("/").pop() ?? "").toLowerCase()
          : "";
      return categoryFilenames.get(basename) ?? "other";
    }

    /** @param {unknown} extension */
    function distributionKeyForExtension(extension) {
      const normalized = normalizeExtension(extension);
      const match = matchExtension(normalized);
      return match ? `${FAMILY_KEY_PREFIX}${match.family.id}` : normalized;
    }

    return Object.freeze({
      categories: frozenCategories,
      families: frozenFamilies,
      matchExtension,
      canonicalExtension,
      categoryForFile,
      distributionKeyForExtension,
    });
  }

  global.MetabrowserFileTypeTaxonomy = createRuntime(
    global.METABROWSER_SETTINGS?.FILE_TYPE_TAXONOMY,
  );
})(window);
