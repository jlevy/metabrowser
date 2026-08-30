/**
 * Immutable browser adapter for the server-owned file-type definitions.
 *
 * New code consumes groups, families, kinds, and registry identity from this
 * runtime. Compatibility aliases remain on the public SDK, but the page embeds one
 * authoritative registry payload rather than parallel projections.
 */

((global) => {
  if (global.MetabrowserFileTypeTaxonomy) {
    return;
  }

  const FAMILY_KEY_PREFIX = "family:";
  const NO_EXTENSION_KEY = "(none)";
  const REMAINING_KEY = "";
  const VALID_ID = /^[a-z][a-z0-9-]*$/;
  const CONTENT_FAMILIES = new Set(["code", "prose", "markup", "data", "binary", "unknown"]);

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
  function integerValue(value, label) {
    if (!Number.isInteger(value)) {
      throw new TypeError(`${label} must be an integer`);
    }
    return /** @type {number} */ (value);
  }

  /** @param {unknown} value @param {string} label */
  function hueValue(value, label) {
    if (typeof value !== "number" || !Number.isFinite(value) || value < 0 || value >= 360) {
      throw new TypeError(`${label} must be a hue in [0, 360) degrees`);
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

  /** @param {unknown} rawRegistry */
  function createRuntime(rawRegistry) {
    const raw = objectValue(rawRegistry, "FILE_TYPE_REGISTRY");
    if (raw.schema !== "file-type-registry-v4" || raw.schema_version !== 4) {
      throw new TypeError("unsupported file-type registry schema");
    }
    const revision = integerValue(raw.revision, "file-type registry revision");
    if (revision < 1) {
      throw new TypeError("file-type registry revision must be positive");
    }
    const fingerprint = stringValue(raw.fingerprint, "file-type registry fingerprint");
    const maxExtensionComponents = integerValue(
      raw.max_extension_components,
      "maximum extension components",
    );
    if (maxExtensionComponents !== 2) {
      throw new TypeError("the recommended file-type profile requires two extension components");
    }
    if (!Array.isArray(raw.groups) || !Array.isArray(raw.families) || !Array.isArray(raw.kinds)) {
      throw new TypeError("FILE_TYPE_REGISTRY must contain group, family, and kind arrays");
    }

    const groupIds = new Set();
    const groupOrders = new Set();
    const groups = raw.groups.map((candidate) => {
      const value = objectValue(candidate, "file type group");
      const id = stringValue(value.id, "file type group id");
      const order = integerValue(value.order, `order for ${id}`);
      if (!VALID_ID.test(id) || groupIds.has(id) || groupOrders.has(order)) {
        throw new TypeError(`invalid or duplicate file type group: ${id}`);
      }
      groupIds.add(id);
      groupOrders.add(order);
      return Object.freeze({
        id,
        label: stringValue(value.label, `label for ${id}`),
        order,
        // Required: every family must resolve to a shape without declaring one.
        icon: stringValue(value.icon, `icon for ${id}`),
      });
    });
    if (!groupIds.has("other")) {
      throw new TypeError("file-type registry must declare the other fallback group");
    }

    const familyIds = new Set();
    const families = raw.families.map((candidate) => {
      const value = objectValue(candidate, "file type family");
      const id = stringValue(value.id, "file type family id");
      const groupId = stringValue(value.group_id, `group for ${id}`);
      if (!VALID_ID.test(id) || familyIds.has(id) || !groupIds.has(groupId)) {
        throw new TypeError(`invalid file type family: ${id}`);
      }
      familyIds.add(id);
      const extensions = stringArray(value.extensions, `extensions for ${id}`);
      for (const extension of extensions) {
        if (normalizeExtension(extension) !== extension || !extension.startsWith(".")) {
          throw new TypeError(`file type family extensions must be normalized: ${extension}`);
        }
      }
      return Object.freeze({
        id,
        label: stringValue(value.label, `label for ${id}`),
        groupId,
        category: groupId,
        // The family's own shape, or null to take its group's. The split is
        // what keeps 56 families down to six shapes: icon is the major type,
        // colour is the subtype.
        icon: value.icon == null ? null : stringValue(value.icon, `icon for ${id}`),
        order: integerValue(value.order, `order for ${id}`),
        extensions,
        // The family's whole color. Lightness and chroma live in the
        // stylesheet, one pair per theme, so a family is a hue and nothing
        // else — see color_oklch.py for why that is the entire rule.
        hue: hueValue(value.hue, `hue for ${id}`),
        linguist:
          value.linguist === null ? null : stringValue(value.linguist, `linguist for ${id}`),
      });
    });
    const familiesById = new Map(families.map((family) => [family.id, family]));

    const extensionEvidence = new Set();
    const filenameEvidence = new Set();
    const kinds = raw.kinds.map((candidate) => {
      const value = objectValue(candidate, "file type kind");
      const id = stringValue(value.id, "file type kind id");
      const familyId =
        value.family_id === null ? null : stringValue(value.family_id, `family for ${id}`);
      const groupId = stringValue(value.group_id, `group for ${id}`);
      const contentFamilyValue = stringValue(value.content_family, `content family for ${id}`);
      if (
        !VALID_ID.test(id) ||
        (familyId !== null && !familyIds.has(familyId)) ||
        !groupIds.has(groupId) ||
        (familyId !== null && familiesById.get(familyId)?.groupId !== groupId) ||
        !CONTENT_FAMILIES.has(contentFamilyValue)
      ) {
        throw new TypeError(`invalid file type kind: ${id}`);
      }
      const contentFamily =
        /** @type {"code" | "prose" | "markup" | "data" | "binary" | "unknown"} */ (
          contentFamilyValue
        );
      const extensions = stringArray(value.extensions, `extensions for ${id}`);
      const filenames = stringArray(value.filenames, `filenames for ${id}`);
      const shebangs = stringArray(value.shebangs, `shebangs for ${id}`);
      for (const extension of extensions) {
        const normalized = normalizeExtension(extension);
        if (
          normalized !== extension ||
          !extension.startsWith(".") ||
          extensionEvidence.has(extension)
        ) {
          throw new TypeError(`invalid or duplicate extension evidence: ${extension}`);
        }
        extensionEvidence.add(extension);
      }
      for (const filename of filenames) {
        const normalized = filename.toLowerCase();
        if (filename !== normalized || filenameEvidence.has(normalized)) {
          throw new TypeError(`invalid or duplicate filename evidence: ${filename}`);
        }
        filenameEvidence.add(normalized);
      }
      return Object.freeze({
        id,
        familyId,
        groupId,
        contentFamily,
        extensions,
        filenames,
        shebangs,
        priority: integerValue(value.priority, `priority for ${id}`),
      });
    });

    const exactExtensions = new Map();
    const exactFilenames = new Map();
    for (const kind of kinds) {
      for (const extension of kind.extensions) {
        exactExtensions.set(extension, kind);
      }
      for (const filename of kind.filenames) {
        exactFilenames.set(filename, kind);
      }
    }
    const suffixes = [...exactExtensions.entries()].sort(
      (left, right) =>
        right[0].split(".").length - left[0].split(".").length ||
        right[0].length - left[0].length ||
        right[1].priority - left[1].priority ||
        left[0].localeCompare(right[0]),
    );

    /** @param {unknown} name @param {unknown} extension */
    function match(name, extension) {
      const basename =
        typeof name === "string"
          ? (name.replace(/\\/g, "/").split("/").pop() ?? "").toLowerCase()
          : "";
      const basenameKind = exactFilenames.get(basename);
      if (basenameKind) {
        return Object.freeze({
          kind: basenameKind,
          canonicalExtension: null,
          detectionSource: "basename",
          confidence: "exact",
        });
      }
      const normalized = normalizeExtension(extension);
      if (!normalized.startsWith(".")) {
        return null;
      }
      const exactKind = exactExtensions.get(normalized);
      if (exactKind) {
        return Object.freeze({
          kind: exactKind,
          canonicalExtension: normalized,
          detectionSource: "extension",
          confidence: "exact",
        });
      }
      for (const [suffix, kind] of suffixes) {
        if (extensionMatches(normalized, suffix)) {
          return Object.freeze({
            kind,
            canonicalExtension: suffix,
            detectionSource: "suffix",
            confidence: "suffix",
          });
        }
      }
      return null;
    }

    /** @param {unknown} name @param {unknown} extension */
    function classify(name, extension) {
      const logicalExtension = normalizeExtension(extension);
      const result = match(name, logicalExtension);
      if (!result) {
        return Object.freeze({
          logicalExtension: logicalExtension || null,
          canonicalExtension: null,
          kindId: null,
          familyId: null,
          groupId: "other",
          contentFamily: "unknown",
          detectionSource: "unknown",
          confidence: "unknown",
          registryRevision: revision,
          registryFingerprint: fingerprint,
        });
      }
      return Object.freeze({
        logicalExtension: logicalExtension || null,
        canonicalExtension: result.canonicalExtension,
        kindId: result.kind.id,
        familyId: result.kind.familyId,
        groupId: result.kind.groupId,
        contentFamily: result.kind.contentFamily,
        detectionSource: result.detectionSource,
        confidence: result.confidence,
        registryRevision: revision,
        registryFingerprint: fingerprint,
      });
    }

    /** @param {unknown} extension */
    function matchExtension(extension) {
      const result = match("", extension);
      const family = result?.kind.familyId ? familiesById.get(result.kind.familyId) : null;
      return family && result?.canonicalExtension
        ? Object.freeze({ family, canonicalExtension: result.canonicalExtension })
        : null;
    }

    /** @param {unknown} extension */
    function canonicalExtension(extension) {
      const normalized = normalizeExtension(extension);
      return matchExtension(normalized)?.canonicalExtension ?? normalized;
    }

    /** @param {unknown} name @param {unknown} extension */
    function groupForFile(name, extension) {
      return classify(name, extension).groupId;
    }

    /** @param {unknown} extension */
    /**
     * The icon name a family paints with: its own, or its group's.
     *
     * Here rather than in each caller because the fallback is the rule, and a
     * rule implemented twice is how this project ended up with two taxonomies
     * disagreeing about `.jsx`.
     * @param {unknown} familyId
     */
    function iconForFamily(familyId) {
      const family = frozenFamilies.find((entry) => entry.id === familyId);
      if (!family) {
        return null;
      }
      const group = frozenGroups.find((entry) => entry.id === family.groupId);
      return family.icon || group?.icon || null;
    }

    /** @param {unknown} extension */
    function distributionKeyForExtension(extension) {
      const normalized = normalizeExtension(extension);
      if (normalized === NO_EXTENSION_KEY) {
        return REMAINING_KEY;
      }
      const family = matchExtension(normalized)?.family;
      return family ? `${FAMILY_KEY_PREFIX}${family.id}` : normalized;
    }

    /**
     * The hue for a distribution key, or null where there is no family behind
     * it — the remaining-types bucket and the extensions inside it, which the
     * palette colors on its own.
     * @param {unknown} key
     */
    function hueForDistributionKey(key) {
      if (typeof key !== "string" || !key.startsWith(FAMILY_KEY_PREFIX)) {
        return null;
      }
      return familiesById.get(key.slice(FAMILY_KEY_PREFIX.length))?.hue ?? null;
    }

    const frozenGroups = Object.freeze(groups);
    const frozenFamilies = Object.freeze(families);
    return Object.freeze({
      schema: "file-type-registry-v4",
      schemaVersion: 4,
      revision,
      fingerprint,
      maxExtensionComponents,
      registryIdentity: Object.freeze({ schemaVersion: 4, revision, fingerprint }),
      groups: frozenGroups,
      families: frozenFamilies,
      kinds: Object.freeze(kinds),
      classify,
      matchExtension,
      canonicalExtension,
      groupForFile,
      distributionKeyForExtension,
      hueForDistributionKey,
      iconForFamily,
    });
  }

  global.MetabrowserFileTypeTaxonomy = createRuntime(
    global.METABROWSER_SETTINGS?.FILE_TYPE_REGISTRY,
  );
})(window);
