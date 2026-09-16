// Browser-side validator for the provider-neutral ChangeRequest format kernel.
//
// This module has no DOM, network, or plugin-registration dependency. The Python and
// browser implementations are held to the same packaged conformance corpus.

const CHANGE_REQUEST_STATES = new Set(["open", "closed", "merged", "unknown"]);
const REVISION_AVAILABILITY = new Set(["present", "unavailable", "not_requested"]);
const REVIEW_DECISIONS = new Set([
  "required",
  "approved",
  "changes_requested",
  "not_requested",
  "unknown",
]);
const MIN_CALENDAR_YEAR = 1;
const MIN_MONTH = 1;
const MAX_MONTH = 12;
const MAX_HOUR = 23;
const MAX_MINUTE = 59;
const MAX_SECOND = 59;
const FEBRUARY_INDEX = 1;
const LEAP_YEAR_FEBRUARY_DAYS = 29;
const COMMON_YEAR_MONTH_DAYS = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31];
const MAX_PORT = 65_535;
const DEFAULT_HTTPS_PORT = 443;
const MAX_PROVIDER_KIND_LENGTH = 63;
const MAX_DNS_HOST_LENGTH = 253;
const PROVIDER_KIND_RE = /^[a-z][a-z0-9-]*$/;
const PROVIDER_INSTANCE_RE =
  /^([a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?(?:\.[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?)*)(?::([1-9][0-9]{0,4}))?$/;
const OID_RE = /^[0-9a-f]{40,64}$/;
const CANONICAL_HTTPS_RE =
  /^https:\/\/([a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?(?:\.[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?)*)(?::([1-9]\d{0,4}))?((?:[/?#][A-Za-z0-9._~:/?#[\]@!$&'()*+,;=%-]*)?)$/;
const NONCANONICAL_PERCENT_RE = /%(?![0-9A-F]{2})/;
const RFC3339_UTC_RE = /^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2}):(\d{2})(?:\.(\d{3}))?Z$/;

class FormatError extends Error {}

/** @param {boolean} condition @param {string} message @returns {asserts condition} */
function require(condition, message) {
  if (!condition) {
    throw new FormatError(message);
  }
}

/** @param {unknown} value @param {string} where @returns {Record<string, unknown>} */
function asObject(value, where) {
  require(typeof value === "object" &&
    value !== null &&
    !Array.isArray(value), `${where}: object required`);
  return /** @type {Record<string, unknown>} */ (value);
}

/** @param {unknown} value @param {string} where @returns {unknown[]} */
function asArray(value, where) {
  require(Array.isArray(value), `${where}: array required`);
  return value;
}

/** @param {Record<string, unknown>} value @param {string[]} allowed @param {string} where */
function forbidExtras(value, allowed, where) {
  for (const key of Object.keys(value)) {
    require(allowed.includes(key), `${where}: unknown key ${key}`);
  }
}

/** @param {unknown} value @param {string} where @returns {string} */
function nonemptyString(value, where) {
  require(typeof value === "string" && value.length > 0, `${where}: nonempty string required`);
  return value;
}

/** @param {unknown} value @param {string} where @returns {string} */
function providerKind(value, where) {
  const text = nonemptyString(value, where);
  require(text.length <= MAX_PROVIDER_KIND_LENGTH &&
    PROVIDER_KIND_RE.test(text), `${where}: canonical provider kind required`);
  return text;
}

/** @param {unknown} value @param {string} where @returns {string} */
function providerInstance(value, where) {
  const text = nonemptyString(value, where);
  const match = PROVIDER_INSTANCE_RE.exec(text);
  require(match !== null, `${where}: canonical provider instance required`);
  require(match[1].length <= MAX_DNS_HOST_LENGTH, `${where}: DNS host is too long`);
  const portText = match[2];
  if (portText !== undefined) {
    const port = Number(portText);
    require(port !== DEFAULT_HTTPS_PORT && port <= MAX_PORT, `${where}: noncanonical port`);
  }
  return text;
}

/** @param {unknown} value @param {string} where */
function nullableString(value, where) {
  require(value === null ||
    (typeof value === "string" && value.length > 0), `${where}: null or string required`);
}

/** @param {unknown} value @param {string} where @returns {string} */
function httpsUrl(value, where) {
  const text = nonemptyString(value, where);
  const match = CANONICAL_HTTPS_RE.exec(text);
  require(match !== null, `${where}: credential-free canonical HTTPS URL required`);
  require(match[1].length <= MAX_DNS_HOST_LENGTH, `${where}: DNS host is too long`);
  const portText = match[2];
  if (portText !== undefined) {
    const port = Number(portText);
    require(port !== DEFAULT_HTTPS_PORT && port <= MAX_PORT, `${where}: noncanonical port`);
  }
  require(!NONCANONICAL_PERCENT_RE.test(match[3]), `${where}: invalid percent escape`);
  return text;
}

/** @param {unknown} value @param {string} where @returns {string} */
function timestamp(value, where) {
  const text = nonemptyString(value, where);
  const match = RFC3339_UTC_RE.exec(text);
  require(match !== null, `${where}: canonical RFC 3339 UTC required`);
  const [, yearText, monthText, dayText, hourText, minuteText, secondText, millisecondText] = match;
  require(millisecondText === undefined ||
    millisecondText !== "000", `${where}: zero milliseconds must be omitted`);
  const year = Number(yearText);
  const month = Number(monthText);
  const day = Number(dayText);
  const hour = Number(hourText);
  const minute = Number(minuteText);
  const second = Number(secondText);
  const isLeapYear = year % 4 === 0 && (year % 100 !== 0 || year % 400 === 0);
  const daysInMonth = [...COMMON_YEAR_MONTH_DAYS];
  if (isLeapYear) {
    daysInMonth[FEBRUARY_INDEX] = LEAP_YEAR_FEBRUARY_DAYS;
  }
  require(year >= MIN_CALENDAR_YEAR &&
    month >= MIN_MONTH &&
    month <= MAX_MONTH &&
    day >= 1 &&
    day <= daysInMonth[month - 1] &&
    hour <= MAX_HOUR &&
    minute <= MAX_MINUTE &&
    second <= MAX_SECOND, `${where}: invalid RFC 3339 date-time`);
  return text;
}

/** @param {unknown} value @param {string} where */
function nonnegativeInteger(value, where) {
  require(Number.isSafeInteger(value) &&
    Number(value) >= 0, `${where}: safe nonnegative integer required`);
}

/** @param {unknown} raw @param {string} where */
function validateProviderObjectRef(raw, where) {
  const value = asObject(raw, where);
  forbidExtras(value, ["provider", "instance", "object_kind", "opaque_id"], where);
  providerKind(value.provider, `${where}.provider`);
  providerInstance(value.instance, `${where}.instance`);
  nonemptyString(value.object_kind, `${where}.object_kind`);
  nonemptyString(value.opaque_id, `${where}.opaque_id`);
}

/** @param {unknown} raw @param {string} where */
function validateRepositoryRef(raw, where) {
  const value = asObject(raw, where);
  forbidExtras(value, ["provider", "instance", "opaque_id"], where);
  providerKind(value.provider, `${where}.provider`);
  providerInstance(value.instance, `${where}.instance`);
  nonemptyString(value.opaque_id, `${where}.opaque_id`);
}

/** @param {unknown} raw @param {string} where */
function validateActorRef(raw, where) {
  const value = asObject(raw, where);
  forbidExtras(value, ["provider_opaque_id", "handle", "url"], where);
  nonemptyString(value.provider_opaque_id, `${where}.provider_opaque_id`);
  nonemptyString(value.handle, `${where}.handle`);
  httpsUrl(value.url, `${where}.url`);
}

/** @param {unknown} raw @param {string} where */
function validateRevisionRef(raw, where) {
  const value = asObject(raw, where);
  forbidExtras(value, ["repository_id", "ref", "oid", "availability"], where);
  nonemptyString(value.repository_id, `${where}.repository_id`);
  nonemptyString(value.ref, `${where}.ref`);
  require("oid" in value, `${where}.oid: required`);
  nullableString(value.oid, `${where}.oid`);
  const availability = nonemptyString(value.availability, `${where}.availability`);
  require(REVISION_AVAILABILITY.has(availability), `${where}.availability: unknown value`);
  if (value.oid !== null) {
    require(OID_RE.test(String(value.oid)), `${where}.oid: full lowercase Git object ID required`);
  }
  require((value.oid !== null) ===
    (availability === "present"), `${where}: oid is present exactly when availability is present`);
}

/** @param {unknown} raw @param {string} where */
function validateComparisonRef(raw, where) {
  const value = asObject(raw, where);
  forbidExtras(value, ["base", "head", "merge_commit_oid", "merge_commit_availability"], where);
  validateRevisionRef(value.base, `${where}.base`);
  validateRevisionRef(value.head, `${where}.head`);
  require("merge_commit_oid" in value, `${where}.merge_commit_oid: required`);
  nullableString(value.merge_commit_oid, `${where}.merge_commit_oid`);
  const availability = nonemptyString(
    value.merge_commit_availability,
    `${where}.merge_commit_availability`,
  );
  require(REVISION_AVAILABILITY.has(availability), `${where}: unknown merge availability`);
  if (value.merge_commit_oid !== null) {
    require(OID_RE.test(String(value.merge_commit_oid)), `${where}: invalid merge commit oid`);
  }
  require((value.merge_commit_oid !== null) ===
    (availability ===
      "present"), `${where}: merge commit oid is present exactly when availability is present`);
}

/** @param {unknown} raw @param {string} where */
function validateLabelRef(raw, where) {
  const value = asObject(raw, where);
  forbidExtras(value, ["name", "color"], where);
  nonemptyString(value.name, `${where}.name`);
  if (value.color !== undefined && value.color !== null) {
    require(typeof value.color === "string" &&
      /^[0-9a-fA-F]{6}$/.test(value.color), `${where}.color: invalid RGB color`);
  }
}

/** @param {unknown} raw @param {string} where */
function validateMilestoneRef(raw, where) {
  const value = asObject(raw, where);
  forbidExtras(value, ["provider_opaque_id", "title", "url"], where);
  nonemptyString(value.provider_opaque_id, `${where}.provider_opaque_id`);
  nonemptyString(value.title, `${where}.title`);
  httpsUrl(value.url, `${where}.url`);
}

/** @param {unknown} raw @param {string} where */
function validateReviewSummary(raw, where) {
  const value = asObject(raw, where);
  forbidExtras(value, ["decision", "requested_people", "requested_teams"], where);
  const decision = nonemptyString(value.decision, `${where}.decision`);
  require(REVIEW_DECISIONS.has(decision), `${where}.decision: unknown value`);
  for (const [index, actor] of asArray(
    value.requested_people,
    `${where}.requested_people`,
  ).entries()) {
    validateActorRef(actor, `${where}.requested_people[${index}]`);
  }
  for (const [index, team] of asArray(
    value.requested_teams,
    `${where}.requested_teams`,
  ).entries()) {
    nonemptyString(team, `${where}.requested_teams[${index}]`);
  }
}

/** @param {unknown} raw @param {string} where */
function validateCounts(raw, where) {
  const value = asObject(raw, where);
  forbidExtras(value, ["commits", "discussion_comments", "reviews"], where);
  nonnegativeInteger(value.commits, `${where}.commits`);
  nonnegativeInteger(value.discussion_comments, `${where}.discussion_comments`);
  nonnegativeInteger(value.reviews, `${where}.reviews`);
}

/** @param {Record<string, unknown>} document */
function validateLifecycle(document) {
  const state = nonemptyString(document.state, "change_request.state");
  require(CHANGE_REQUEST_STATES.has(state), "change_request.state: unknown value");
  const created = Date.parse(timestamp(document.created_at, "change_request.created_at"));
  const updated = Date.parse(timestamp(document.updated_at, "change_request.updated_at"));
  require(updated >= created, "change_request.updated_at precedes created_at");
  require("closed_at" in document &&
    "merged_at" in document, "change_request: lifecycle timestamps required");
  nullableString(document.closed_at, "change_request.closed_at");
  nullableString(document.merged_at, "change_request.merged_at");
  for (const [name, value] of [
    ["closed_at", document.closed_at],
    ["merged_at", document.merged_at],
  ]) {
    if (value !== null) {
      const observed = Date.parse(timestamp(value, `change_request.${name}`));
      require(observed >= created &&
        observed <= updated, `change_request.${name}: outside lifecycle`);
    }
  }
  if (state === "open") {
    require(document.closed_at === null &&
      document.merged_at === null, "open change request has lifecycle end");
  } else if (state === "closed") {
    require(document.closed_at !== null &&
      document.merged_at === null, "closed change request timestamps disagree");
  } else if (state === "merged") {
    require(document.closed_at !== null &&
      document.merged_at !== null, "merged change request timestamps required");
  }
}

/**
 * @typedef {{ok: true, value: Record<string, unknown>} | {ok: false, error: string}} ParseResult
 */

/** @param {unknown} raw @returns {ParseResult} */
export function parseChangeRequest(raw) {
  try {
    const document = asObject(raw, "change_request");
    forbidExtras(
      document,
      [
        "id",
        "provider_ref",
        "repository",
        "number",
        "url",
        "title",
        "author",
        "state",
        "draft",
        "locked",
        "created_at",
        "updated_at",
        "closed_at",
        "merged_at",
        "comparison",
        "labels",
        "assignees",
        "milestone",
        "review",
        "counts",
      ],
      "change_request",
    );
    nonemptyString(document.id, "change_request.id");
    validateProviderObjectRef(document.provider_ref, "change_request.provider_ref");
    validateRepositoryRef(document.repository, "change_request.repository");
    nonnegativeInteger(document.number, "change_request.number");
    require(Number(document.number) >= 1, "change_request.number: integer >= 1 required");
    httpsUrl(document.url, "change_request.url");
    nonemptyString(document.title, "change_request.title");
    validateActorRef(document.author, "change_request.author");
    require(typeof document.draft === "boolean", "change_request.draft: boolean required");
    require(typeof document.locked === "boolean", "change_request.locked: boolean required");
    validateLifecycle(document);
    validateComparisonRef(document.comparison, "change_request.comparison");
    for (const [index, label] of asArray(document.labels, "change_request.labels").entries()) {
      validateLabelRef(label, `change_request.labels[${index}]`);
    }
    for (const [index, actor] of asArray(
      document.assignees,
      "change_request.assignees",
    ).entries()) {
      validateActorRef(actor, `change_request.assignees[${index}]`);
    }
    require("milestone" in document, "change_request.milestone: required");
    if (document.milestone !== null) {
      validateMilestoneRef(document.milestone, "change_request.milestone");
    }
    validateReviewSummary(document.review, "change_request.review");
    validateCounts(document.counts, "change_request.counts");

    const provider = asObject(document.provider_ref, "change_request.provider_ref");
    const repository = asObject(document.repository, "change_request.repository");
    require(provider.provider === repository.provider &&
      provider.instance === repository.instance, "change_request: provider instance mismatch");
    const comparison = asObject(document.comparison, "change_request.comparison");
    const base = asObject(comparison.base, "change_request.comparison.base");
    require(base.repository_id ===
      repository.opaque_id, "change_request: base repository mismatch");
    return { ok: true, value: document };
  } catch (error) {
    if (!(error instanceof FormatError)) {
      throw error;
    }
    return { ok: false, error: error instanceof Error ? error.message : String(error) };
  }
}
