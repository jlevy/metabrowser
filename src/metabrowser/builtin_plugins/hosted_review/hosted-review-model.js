// Browser-side validator for the provider-neutral ChangeRequest format kernel.
//
// This module has no DOM, network, or plugin-registration dependency. The Python and
// browser implementations are held to the same packaged conformance corpus.

const CHANGE_REQUEST_STATES = new Set(["open", "closed", "merged", "unknown"]);
const REVISION_OBSERVATIONS = new Set(["observed", "unavailable", "not_requested"]);
const REVIEW_DECISIONS = new Set([
  "required",
  "approved",
  "changes_requested",
  "not_requested",
  "unknown",
]);
const COMMENT_STATES = new Set(["visible", "minimized", "deleted", "unknown"]);
const REVIEW_DISPOSITIONS = new Set([
  "pending",
  "commented",
  "approved",
  "changes_requested",
  "dismissed",
  "unknown",
]);
const REVIEW_THREAD_STATES = new Set(["unresolved", "resolved", "unknown"]);
const REVIEW_ANCHOR_STATES = new Set(["current", "outdated", "unresolved", "unmappable"]);
const REVIEW_SIDES = new Set(["base", "head"]);
const CHECK_KINDS = new Set(["suite", "run", "unknown"]);
const CHECK_STATUSES = new Set([
  "queued",
  "in_progress",
  "completed",
  "waiting",
  "requested",
  "pending",
  "unknown",
]);
const CHECK_CONCLUSIONS = new Set([
  "action_required",
  "cancelled",
  "failure",
  "neutral",
  "skipped",
  "stale",
  "startup_failure",
  "success",
  "timed_out",
  "unknown",
]);
const COMMIT_STATUS_STATES = new Set(["error", "failure", "pending", "success", "unknown"]);
const REPOSITORY_VISIBILITIES = new Set(["public", "internal", "private", "unknown"]);
const DEFAULT_BRANCH_AVAILABILITY = new Set(["present", "absent", "unavailable", "unknown"]);
const INDEX_SORT_FIELDS = new Set(["created_at", "updated_at"]);
const SORT_DIRECTIONS = new Set(["ascending", "descending"]);
const ACTIVITY_KINDS = new Set(["commit", "change_request"]);
const ACTIVITY_STATES = new Set(["open", "draft", "closed", "merged", "unknown"]);
const ACTIVITY_COVERAGE = new Set(["complete", "partial"]);
const TRUNCATION_REASONS = new Set([
  "item_bound",
  "page_bound",
  "byte_bound",
  "time_bound",
  "provider_limit",
  "provider_failure",
  "malformed_response",
  "cancelled",
]);
const BOUNDED_TRUNCATION_REASONS = new Set([
  "item_bound",
  "page_bound",
  "byte_bound",
  "time_bound",
  "provider_limit",
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
const MAX_OPAQUE_CURSOR_LENGTH = 4096;
// Text bounds mirror models.py, which records the basis for each value. Lengths count
// Unicode code points, as Python does, not UTF-16 code units.
const MAX_PROVIDER_ID_LENGTH = 255;
const MAX_DOMAIN_ID_LENGTH = 1024;
const MAX_LINE_TEXT_LENGTH = 1024;
const MAX_HANDLE_LENGTH = 255;
const MAX_URL_LENGTH = 8192;
// Review-anchor paths carry a length bound only; a checkout path is not display text.
const MAX_REVIEW_PATH_LENGTH = 4096;
const MAX_REVIEW_PATH_B64_LENGTH = 5464;
const FIRST_SURROGATE = 0xd800;
const LAST_SURROGATE = 0xdfff;
// Inclusive code point ranges; explicit so both runtimes agree across Unicode versions.
const CONTROL_AND_LINE_SEPARATOR_RANGES = [
  [0x0000, 0x001f],
  [0x007f, 0x009f],
  [0x2028, 0x2029],
];
const IDENTIFIER_FORBIDDEN_RANGES = [
  ...CONTROL_AND_LINE_SEPARATOR_RANGES,
  [0x061c, 0x061c],
  [0x200b, 0x200f],
  [0x202a, 0x202e],
  [0x2060, 0x2069],
  [0xfeff, 0xfeff],
];
const PROVIDER_KIND_RE = /^[a-z][a-z0-9-]*$/;
const PROVIDER_INSTANCE_RE =
  /^([a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?(?:\.[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?)*)(?::([1-9][0-9]{0,4}))?$/;
// A full Git object name is SHA-1 (40 hex) or SHA-256 (64 hex); nothing in between.
const OID_RE = /^(?:[0-9a-f]{40}|[0-9a-f]{64})$/;
const SHA256_RE = /^sha256:[0-9a-f]{64}$/;
const OPAQUE_CURSOR_RE = /^[A-Za-z0-9._~+=:-]+$/;
const URI_SCHEME_RE = /^[A-Za-z][A-Za-z0-9+.-]*:/;
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
  utf8Bytes(value, where);
  return value;
}

/**
 * A nonempty well-formed string of at most `maxLength` code points, none in `forbidden`.
 * @param {unknown} value @param {number} maxLength @param {number[][]} forbidden
 * @param {string} where @returns {string}
 */
function boundedText(value, maxLength, forbidden, where) {
  const text = nonemptyString(value, where);
  let length = 0;
  for (const character of text) {
    const codePoint = /** @type {number} */ (character.codePointAt(0));
    length += 1;
    require(codePoint < FIRST_SURROGATE || codePoint > LAST_SURROGATE, `${where}: lone surrogate`);
    require(!forbidden.some(
      ([low, high]) => codePoint >= low && codePoint <= high,
    ), `${where}: forbidden control or formatting character`);
  }
  require(length <= maxLength, `${where}: longer than ${maxLength} characters`);
  return text;
}

/** @param {unknown} value @param {string} where @returns {string} */
function providerId(value, where) {
  return boundedText(value, MAX_PROVIDER_ID_LENGTH, IDENTIFIER_FORBIDDEN_RANGES, where);
}

/** @param {unknown} value @param {string} where @returns {string} */
function domainId(value, where) {
  return boundedText(value, MAX_DOMAIN_ID_LENGTH, IDENTIFIER_FORBIDDEN_RANGES, where);
}

/** @param {unknown} value @param {string} where @returns {string} */
function lineText(value, where) {
  return boundedText(value, MAX_LINE_TEXT_LENGTH, CONTROL_AND_LINE_SEPARATOR_RANGES, where);
}

/** @param {unknown} value @param {string} where @returns {string} */
function handle(value, where) {
  return boundedText(value, MAX_HANDLE_LENGTH, CONTROL_AND_LINE_SEPARATOR_RANGES, where);
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
  if (typeof value === "string") {
    utf8Bytes(value, where);
  }
}

/** @param {unknown} value @param {string} where @returns {string} */
function httpsUrl(value, where) {
  const text = nonemptyString(value, where);
  require(text.length <= MAX_URL_LENGTH, `${where}: URL is too long`);
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

/** @param {unknown} value @param {string} where */
function positiveInteger(value, where) {
  nonnegativeInteger(value, where);
  require(Number(value) >= 1, `${where}: positive integer required`);
}

/** @param {unknown} value @param {Set<string>} allowed @param {string} where @returns {string} */
function enumValue(value, allowed, where) {
  const text = nonemptyString(value, where);
  require(allowed.has(text), `${where}: unknown value`);
  return text;
}

/** @param {unknown} value @param {string} where @returns {string} */
function sha256Digest(value, where) {
  const text = nonemptyString(value, where);
  require(SHA256_RE.test(text), `${where}: lowercase sha256 digest required`);
  return text;
}

/** @param {string} value @param {string} where @returns {Uint8Array} */
function utf8Bytes(value, where) {
  for (let index = 0; index < value.length; index += 1) {
    const codeUnit = value.charCodeAt(index);
    if (codeUnit >= 0xd800 && codeUnit <= 0xdbff) {
      const next = value.charCodeAt(index + 1);
      require(next >= 0xdc00 && next <= 0xdfff, `${where}: valid UTF-8 text required`);
      index += 1;
    } else {
      require(!(codeUnit >= 0xdc00 && codeUnit <= 0xdfff), `${where}: valid UTF-8 text required`);
    }
  }
  return new TextEncoder().encode(value);
}

/** @param {string} left @param {string} right @returns {number} */
function compareUtf8(left, right) {
  const leftBytes = utf8Bytes(left, "ordered identifier");
  const rightBytes = utf8Bytes(right, "ordered identifier");
  const length = Math.min(leftBytes.length, rightBytes.length);
  for (let index = 0; index < length; index += 1) {
    if (leftBytes[index] !== rightBytes[index]) {
      return Number(leftBytes[index]) - Number(rightBytes[index]);
    }
  }
  return leftBytes.length - rightBytes.length;
}

const SHA256_INITIAL = new Uint32Array([
  0x6a09e667, 0xbb67ae85, 0x3c6ef372, 0xa54ff53a, 0x510e527f, 0x9b05688c, 0x1f83d9ab, 0x5be0cd19,
]);
const SHA256_ROUNDS = new Uint32Array([
  0x428a2f98, 0x71374491, 0xb5c0fbcf, 0xe9b5dba5, 0x3956c25b, 0x59f111f1, 0x923f82a4, 0xab1c5ed5,
  0xd807aa98, 0x12835b01, 0x243185be, 0x550c7dc3, 0x72be5d74, 0x80deb1fe, 0x9bdc06a7, 0xc19bf174,
  0xe49b69c1, 0xefbe4786, 0x0fc19dc6, 0x240ca1cc, 0x2de92c6f, 0x4a7484aa, 0x5cb0a9dc, 0x76f988da,
  0x983e5152, 0xa831c66d, 0xb00327c8, 0xbf597fc7, 0xc6e00bf3, 0xd5a79147, 0x06ca6351, 0x14292967,
  0x27b70a85, 0x2e1b2138, 0x4d2c6dfc, 0x53380d13, 0x650a7354, 0x766a0abb, 0x81c2c92e, 0x92722c85,
  0xa2bfe8a1, 0xa81a664b, 0xc24b8b70, 0xc76c51a3, 0xd192e819, 0xd6990624, 0xf40e3585, 0x106aa070,
  0x19a4c116, 0x1e376c08, 0x2748774c, 0x34b0bcb5, 0x391c0cb3, 0x4ed8aa4a, 0x5b9cca4f, 0x682e6ff3,
  0x748f82ee, 0x78a5636f, 0x84c87814, 0x8cc70208, 0x90befffa, 0xa4506ceb, 0xbef9a3f7, 0xc67178f2,
]);

/** @param {number} value @param {number} bits @returns {number} */
function rotateRight(value, bits) {
  return (value >>> bits) | (value << (32 - bits));
}

/** @param {string} value @returns {string} */
function sha256Hex(value) {
  const source = utf8Bytes(value, "sha256 input");
  const paddedLength = Math.ceil((source.length + 9) / 64) * 64;
  const padded = new Uint8Array(paddedLength);
  padded.set(source);
  padded[source.length] = 0x80;
  const bitLength = source.length * 8;
  const view = new DataView(padded.buffer);
  view.setUint32(paddedLength - 8, Math.floor(bitLength / 0x1_0000_0000));
  view.setUint32(paddedLength - 4, bitLength >>> 0);
  const hash = new Uint32Array(SHA256_INITIAL);
  const words = new Uint32Array(64);

  for (let offset = 0; offset < paddedLength; offset += 64) {
    for (let index = 0; index < 16; index += 1) {
      words[index] = view.getUint32(offset + index * 4);
    }
    for (let index = 16; index < 64; index += 1) {
      const first = words[index - 15];
      const second = words[index - 2];
      const sigma0 = rotateRight(first, 7) ^ rotateRight(first, 18) ^ (first >>> 3);
      const sigma1 = rotateRight(second, 17) ^ rotateRight(second, 19) ^ (second >>> 10);
      words[index] = (words[index - 16] + sigma0 + words[index - 7] + sigma1) >>> 0;
    }

    let [a, b, c, d, e, f, g, h] = hash;
    for (let index = 0; index < 64; index += 1) {
      const sum1 = rotateRight(e, 6) ^ rotateRight(e, 11) ^ rotateRight(e, 25);
      const choice = (e & f) ^ (~e & g);
      const temporary1 = (h + sum1 + choice + SHA256_ROUNDS[index] + words[index]) >>> 0;
      const sum0 = rotateRight(a, 2) ^ rotateRight(a, 13) ^ rotateRight(a, 22);
      const majority = (a & b) ^ (a & c) ^ (b & c);
      const temporary2 = (sum0 + majority) >>> 0;
      h = g;
      g = f;
      f = e;
      e = (d + temporary1) >>> 0;
      d = c;
      c = b;
      b = a;
      a = (temporary1 + temporary2) >>> 0;
    }
    hash[0] = (hash[0] + a) >>> 0;
    hash[1] = (hash[1] + b) >>> 0;
    hash[2] = (hash[2] + c) >>> 0;
    hash[3] = (hash[3] + d) >>> 0;
    hash[4] = (hash[4] + e) >>> 0;
    hash[5] = (hash[5] + f) >>> 0;
    hash[6] = (hash[6] + g) >>> 0;
    hash[7] = (hash[7] + h) >>> 0;
  }
  return [...hash].map((part) => part.toString(16).padStart(8, "0")).join("");
}

/** @param {unknown} raw @param {string} where */
function validateProviderObjectRef(raw, where) {
  const value = asObject(raw, where);
  forbidExtras(value, ["provider", "instance", "object_kind", "opaque_id"], where);
  providerKind(value.provider, `${where}.provider`);
  providerInstance(value.instance, `${where}.instance`);
  providerId(value.object_kind, `${where}.object_kind`);
  providerId(value.opaque_id, `${where}.opaque_id`);
}

/** @param {unknown} raw @param {string} where */
function validateRepositoryRef(raw, where) {
  const value = asObject(raw, where);
  forbidExtras(value, ["provider", "instance", "opaque_id"], where);
  providerKind(value.provider, `${where}.provider`);
  providerInstance(value.instance, `${where}.instance`);
  providerId(value.opaque_id, `${where}.opaque_id`);
}

/** @param {unknown} raw @param {string} where */
function validateActorRef(raw, where) {
  const value = asObject(raw, where);
  forbidExtras(value, ["provider_opaque_id", "handle", "url"], where);
  providerId(value.provider_opaque_id, `${where}.provider_opaque_id`);
  handle(value.handle, `${where}.handle`);
  httpsUrl(value.url, `${where}.url`);
}

/** @param {unknown} raw @param {string} where */
function validateRevisionRef(raw, where) {
  const value = asObject(raw, where);
  forbidExtras(value, ["repository_id", "ref", "oid", "observation"], where);
  require("repository_id" in value, `${where}.repository_id: required`);
  if (value.repository_id !== null) {
    providerId(value.repository_id, `${where}.repository_id`);
  }
  lineText(value.ref, `${where}.ref`);
  require("oid" in value, `${where}.oid: required`);
  nullableString(value.oid, `${where}.oid`);
  const observation = nonemptyString(value.observation, `${where}.observation`);
  require(REVISION_OBSERVATIONS.has(observation), `${where}.observation: unknown value`);
  if (value.oid !== null) {
    require(OID_RE.test(String(value.oid)), `${where}.oid: full lowercase Git object ID required`);
  }
  require((value.oid !== null) ===
    (observation === "observed"), `${where}: oid is present exactly when the provider observed it`);
}

/** @param {unknown} raw @param {string} where */
function validateComparisonRef(raw, where) {
  const value = asObject(raw, where);
  forbidExtras(value, ["base", "head", "merge_commit_oid", "merge_commit_observation"], where);
  validateRevisionRef(value.base, `${where}.base`);
  validateRevisionRef(value.head, `${where}.head`);
  require("merge_commit_oid" in value, `${where}.merge_commit_oid: required`);
  nullableString(value.merge_commit_oid, `${where}.merge_commit_oid`);
  const observation = nonemptyString(
    value.merge_commit_observation,
    `${where}.merge_commit_observation`,
  );
  require(REVISION_OBSERVATIONS.has(observation), `${where}: unknown merge commit observation`);
  if (value.merge_commit_oid !== null) {
    require(OID_RE.test(String(value.merge_commit_oid)), `${where}: invalid merge commit oid`);
  }
  require((value.merge_commit_oid !== null) ===
    (observation ===
      "observed"), `${where}: merge commit oid is present exactly when the provider observed it`);
}

/** @param {unknown} raw @param {string} where */
function validateLabelRef(raw, where) {
  const value = asObject(raw, where);
  forbidExtras(value, ["name", "color"], where);
  lineText(value.name, `${where}.name`);
  if (value.color !== undefined && value.color !== null) {
    require(typeof value.color === "string" &&
      /^[0-9a-fA-F]{6}$/.test(value.color), `${where}.color: invalid RGB color`);
  }
}

/** @param {unknown} raw @param {string} where */
function validateMilestoneRef(raw, where) {
  const value = asObject(raw, where);
  forbidExtras(value, ["provider_opaque_id", "title", "url"], where);
  providerId(value.provider_opaque_id, `${where}.provider_opaque_id`);
  lineText(value.title, `${where}.title`);
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
    lineText(team, `${where}.requested_teams[${index}]`);
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

/** @param {unknown} raw @param {string} where */
function validateGitObjectRef(raw, where) {
  const value = asObject(raw, where);
  forbidExtras(value, ["repository_id", "oid", "observation"], where);
  require("repository_id" in value, `${where}.repository_id: required`);
  if (value.repository_id !== null) {
    providerId(value.repository_id, `${where}.repository_id`);
  }
  require("oid" in value, `${where}.oid: required`);
  nullableString(value.oid, `${where}.oid`);
  const observation = enumValue(value.observation, REVISION_OBSERVATIONS, `${where}.observation`);
  if (value.oid !== null) {
    require(OID_RE.test(String(value.oid)), `${where}.oid: full lowercase Git object ID required`);
  }
  require((value.oid !== null) ===
    (observation === "observed"), `${where}: oid is present exactly when the provider observed it`);
}

/** @param {Record<string, unknown>} provider @param {Record<string, unknown>} repository @param {string} where */
function requireSameProviderInstance(provider, repository, where) {
  require(provider.provider === repository.provider &&
    provider.instance === repository.instance, `${where}: provider instance mismatch`);
}

/** @param {unknown} left @param {unknown} right @returns {boolean} */
function sameRepositoryRef(left, right) {
  const first = asObject(left, "repository");
  const second = asObject(right, "repository");
  return (
    first.provider === second.provider &&
    first.instance === second.instance &&
    first.opaque_id === second.opaque_id
  );
}

/** @param {unknown} left @param {unknown} right @returns {boolean} */
function sameRevisionRef(left, right) {
  const first = asObject(left, "revision");
  const second = asObject(right, "revision");
  return (
    first.repository_id === second.repository_id &&
    first.ref === second.ref &&
    first.oid === second.oid &&
    first.observation === second.observation
  );
}

/** @param {unknown} value @param {string} where */
function validateNullableActor(value, where) {
  if (value !== null) {
    validateActorRef(value, where);
  }
}

/** @param {unknown} value @param {string} where */
function validateNullableUrl(value, where) {
  if (value !== null) {
    httpsUrl(value, where);
  }
}

/** @param {unknown} value @param {string} where */
function validateNullableTimestamp(value, where) {
  if (value !== null) {
    timestamp(value, where);
  }
}

/** @param {unknown} raw @param {string} where */
function validateReviewRangeEndpoint(raw, where) {
  const value = asObject(raw, where);
  forbidExtras(value, ["side", "line"], where);
  enumValue(value.side, REVIEW_SIDES, `${where}.side`);
  positiveInteger(value.line, `${where}.line`);
}

/** @param {string} value @param {string} where @returns {Uint8Array} */
function canonicalBase64Bytes(value, where) {
  let decoded;
  try {
    decoded = atob(value);
  } catch (_error) {
    throw new FormatError(`${where}: canonical base64 required`);
  }
  require(decoded.length > 0 && btoa(decoded) === value, `${where}: canonical base64 required`);
  const bytes = new Uint8Array(decoded.length);
  for (let index = 0; index < decoded.length; index += 1) {
    bytes[index] = decoded.charCodeAt(index);
  }
  return bytes;
}

/** @param {unknown} raw @param {string} where */
function validateReviewAnchor(raw, where) {
  const value = asObject(raw, where);
  const kind = nonemptyString(value.kind, `${where}.kind`);
  const commonKeys = [
    "kind",
    "path",
    "path_b64",
    "comparison",
    "original_revision",
    "current_revision",
    "state",
  ];
  if (kind === "file") {
    forbidExtras(value, commonKeys, where);
  } else if (kind === "line") {
    forbidExtras(value, [...commonKeys, "side", "line"], where);
    enumValue(value.side, REVIEW_SIDES, `${where}.side`);
    positiveInteger(value.line, `${where}.line`);
  } else if (kind === "range") {
    forbidExtras(value, [...commonKeys, "start", "end"], where);
    validateReviewRangeEndpoint(value.start, `${where}.start`);
    validateReviewRangeEndpoint(value.end, `${where}.end`);
    const start = asObject(value.start, `${where}.start`);
    const end = asObject(value.end, `${where}.end`);
    require(start.side !== end.side ||
      Number(start.line) < Number(end.line), `${where}: same-side range endpoints must be ordered`);
  } else {
    throw new FormatError(`${where}.kind: unknown value`);
  }

  const path = boundedText(value.path, MAX_REVIEW_PATH_LENGTH, [], `${where}.path`);
  require(!path.includes("\0"), `${where}.path: NUL is forbidden`);
  require("path_b64" in value, `${where}.path_b64: required`);
  if (value.path_b64 !== null) {
    boundedText(value.path_b64, MAX_REVIEW_PATH_B64_LENGTH, [], `${where}.path_b64`);
  }
  if (value.path_b64 === null) {
    utf8Bytes(path, `${where}.path`);
  } else {
    const bytes = canonicalBase64Bytes(String(value.path_b64), `${where}.path_b64`);
    require(!bytes.includes(0), `${where}.path_b64: NUL is forbidden`);
    const display = new TextDecoder("utf-8", { fatal: false, ignoreBOM: true }).decode(bytes);
    require(display === path, `${where}: path display does not match path_b64`);
  }

  validateComparisonRef(value.comparison, `${where}.comparison`);
  validateGitObjectRef(value.original_revision, `${where}.original_revision`);
  validateGitObjectRef(value.current_revision, `${where}.current_revision`);
  const state = enumValue(value.state, REVIEW_ANCHOR_STATES, `${where}.state`);
  const comparison = asObject(value.comparison, `${where}.comparison`);
  const head = asObject(comparison.head, `${where}.comparison.head`);
  const original = asObject(value.original_revision, `${where}.original_revision`);
  const current = asObject(value.current_revision, `${where}.current_revision`);
  require(original.observation !==
    "not_requested", `${where}: original revision must be requested from the provider`);
  require(original.repository_id ===
    head.repository_id, `${where}: original revision must belong to comparison head`);
  require(current.repository_id ===
    head.repository_id, `${where}: current revision must belong to comparison head`);
  const currentIsObserved = current.observation === "observed";
  require(state === "unresolved" ||
    currentIsObserved, `${where}: resolved anchor states require an observed current revision`);
  if (currentIsObserved) {
    require(head.observation === "observed" &&
      current.repository_id === head.repository_id &&
      current.oid === head.oid, `${where}: current revision must match comparison head`);
  }
}

/** @param {Record<string, unknown>} value @param {string} where */
function validateCommentLifecycle(value, where) {
  const state = enumValue(value.state, COMMENT_STATES, `${where}.state`);
  require("url" in value, `${where}.url: required`);
  validateNullableUrl(value.url, `${where}.url`);
  require(state === "deleted" || value.url !== null, `${where}: visible comments require a URL`);
  const created = Date.parse(timestamp(value.created_at, `${where}.created_at`));
  const updated = Date.parse(timestamp(value.updated_at, `${where}.updated_at`));
  require(updated >= created, `${where}.updated_at precedes created_at`);
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
    domainId(document.id, "change_request.id");
    validateProviderObjectRef(document.provider_ref, "change_request.provider_ref");
    validateRepositoryRef(document.repository, "change_request.repository");
    nonnegativeInteger(document.number, "change_request.number");
    require(Number(document.number) >= 1, "change_request.number: integer >= 1 required");
    httpsUrl(document.url, "change_request.url");
    lineText(document.title, "change_request.title");
    require("author" in document, "change_request.author: required");
    if (document.author !== null) {
      validateActorRef(document.author, "change_request.author");
    }
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
    // The ID is verified against the structured fields, never parsed: an instance may carry
    // a port and an opaque ID may contain the separator, so splitting is ambiguous. The one
    // segment no field supplies is the adapter's separator-free canonical ID kind.
    const id = String(document.id);
    const prefix = `${repository.provider}:${repository.instance}:${repository.opaque_id}:`;
    const suffix = `:${document.number}`;
    const idKind = id.slice(prefix.length, id.length - suffix.length);
    require(id.startsWith(prefix) &&
      id.endsWith(suffix) &&
      id.length > prefix.length + suffix.length &&
      idKind.length <= MAX_PROVIDER_KIND_LENGTH &&
      PROVIDER_KIND_RE.test(idKind), "change_request.id: does not match its structured identity");
    return { ok: true, value: document };
  } catch (error) {
    if (!(error instanceof FormatError)) {
      throw error;
    }
    return { ok: false, error: error instanceof Error ? error.message : String(error) };
  }
}

/**
 * @param {unknown} raw
 * @param {string} where
 * @param {(value: Record<string, unknown>) => void} validate
 * @returns {ParseResult}
 */
function parseRecord(raw, where, validate) {
  try {
    const document = asObject(raw, where);
    validate(document);
    return { ok: true, value: document };
  } catch (error) {
    if (!(error instanceof FormatError)) {
      throw error;
    }
    return { ok: false, error: error.message };
  }
}

/** @param {Record<string, unknown>} value @param {string} where */
function validateHostedIdentity(value, where) {
  domainId(value.id, `${where}.id`);
  validateProviderObjectRef(value.provider_ref, `${where}.provider_ref`);
  validateRepositoryRef(value.repository, `${where}.repository`);
  requireSameProviderInstance(
    asObject(value.provider_ref, `${where}.provider_ref`),
    asObject(value.repository, `${where}.repository`),
    where,
  );
}

/** @param {unknown} raw @returns {ParseResult} */
export function parseHostedRepository(raw) {
  return parseRecord(raw, "hosted_repository", (document) => {
    forbidExtras(
      document,
      [
        "provider_ref",
        "owner",
        "name",
        "url",
        "clone_url",
        "visibility",
        "default_branch",
        "created_at",
        "updated_at",
      ],
      "hosted_repository",
    );
    validateProviderObjectRef(document.provider_ref, "hosted_repository.provider_ref");
    validateActorRef(document.owner, "hosted_repository.owner");
    lineText(document.name, "hosted_repository.name");
    httpsUrl(document.url, "hosted_repository.url");
    httpsUrl(document.clone_url, "hosted_repository.clone_url");
    enumValue(document.visibility, REPOSITORY_VISIBILITIES, "hosted_repository.visibility");
    const defaultBranch = asObject(document.default_branch, "hosted_repository.default_branch");
    forbidExtras(defaultBranch, ["availability", "name"], "hosted_repository.default_branch");
    const availability = enumValue(
      defaultBranch.availability,
      DEFAULT_BRANCH_AVAILABILITY,
      "hosted_repository.default_branch.availability",
    );
    require("name" in defaultBranch, "hosted_repository.default_branch.name: required");
    if (defaultBranch.name !== null) {
      lineText(defaultBranch.name, "hosted_repository.default_branch.name");
    }
    require((defaultBranch.name !== null) ===
      (availability ===
        "present"), "hosted_repository.default_branch: name and availability disagree");
    const created = Date.parse(timestamp(document.created_at, "hosted_repository.created_at"));
    const updated = Date.parse(timestamp(document.updated_at, "hosted_repository.updated_at"));
    require(updated >= created, "hosted_repository.updated_at precedes created_at");
  });
}

/** @param {unknown} raw @param {string} where @returns {Record<string, unknown>} */
function validateChangeRequestIndexQuery(raw, where) {
  const query = asObject(raw, where);
  forbidExtras(query, ["repository", "state_filter", "sort", "bounds"], where);
  validateRepositoryRef(query.repository, `${where}.repository`);

  const stateFilter = asObject(query.state_filter, `${where}.state_filter`);
  const filterKind = nonemptyString(stateFilter.kind, `${where}.state_filter.kind`);
  if (filterKind === "all") {
    forbidExtras(stateFilter, ["kind"], `${where}.state_filter`);
  } else if (filterKind === "selected") {
    forbidExtras(stateFilter, ["kind", "states"], `${where}.state_filter`);
    const states = asArray(stateFilter.states, `${where}.state_filter.states`);
    require(states.length > 0, `${where}.state_filter.states: nonempty array required`);
    let previous = null;
    for (const [index, state] of states.entries()) {
      const current = enumValue(
        state,
        CHANGE_REQUEST_STATES,
        `${where}.state_filter.states[${index}]`,
      );
      require(previous === null ||
        current > previous, `${where}.state_filter.states: sorted unique values required`);
      previous = current;
    }
  } else {
    throw new FormatError(`${where}.state_filter.kind: unknown value`);
  }

  const sort = asObject(query.sort, `${where}.sort`);
  forbidExtras(sort, ["field", "direction", "tie_breaker"], `${where}.sort`);
  enumValue(sort.field, INDEX_SORT_FIELDS, `${where}.sort.field`);
  enumValue(sort.direction, SORT_DIRECTIONS, `${where}.sort.direction`);
  require(sort.tie_breaker ===
    "provider_opaque_id", `${where}.sort.tie_breaker: provider_opaque_id required`);

  const bounds = asObject(query.bounds, `${where}.bounds`);
  forbidExtras(
    bounds,
    ["max_items", "max_pages", "max_bytes", "max_duration_ms"],
    `${where}.bounds`,
  );
  positiveInteger(bounds.max_items, `${where}.bounds.max_items`);
  positiveInteger(bounds.max_pages, `${where}.bounds.max_pages`);
  positiveInteger(bounds.max_bytes, `${where}.bounds.max_bytes`);
  positiveInteger(bounds.max_duration_ms, `${where}.bounds.max_duration_ms`);
  return query;
}

/** @param {Record<string, unknown>} query @returns {string} */
function changeRequestIndexQueryKey(query) {
  const repository = asObject(query.repository, "query.repository");
  const stateFilter = asObject(query.state_filter, "query.state_filter");
  const sort = asObject(query.sort, "query.sort");
  const bounds = asObject(query.bounds, "query.bounds");
  const stateFilterKey =
    stateFilter.kind === "all"
      ? ["all"]
      : ["selected", ...asArray(stateFilter.states, "query.state_filter.states")];
  const value = [
    "ChangeRequestIndexQuery/v1",
    repository.provider,
    repository.instance,
    repository.opaque_id,
    stateFilterKey,
    sort.field,
    sort.direction,
    sort.tie_breaker,
    bounds.max_items,
    bounds.max_pages,
    bounds.max_bytes,
    bounds.max_duration_ms,
  ];
  return `sha256:${sha256Hex(JSON.stringify(value))}`;
}

/** @param {unknown} raw @param {string} where @returns {Record<string, unknown>} */
function validateChangeRequestIndexRow(raw, where) {
  const row = asObject(raw, where);
  forbidExtras(
    row,
    [
      "provider_ref",
      "repository",
      "number",
      "url",
      "title",
      "state",
      "draft",
      "author",
      "base_label",
      "head_label",
      "created_at",
      "updated_at",
    ],
    where,
  );
  validateProviderObjectRef(row.provider_ref, `${where}.provider_ref`);
  validateRepositoryRef(row.repository, `${where}.repository`);
  requireSameProviderInstance(
    asObject(row.provider_ref, `${where}.provider_ref`),
    asObject(row.repository, `${where}.repository`),
    where,
  );
  positiveInteger(row.number, `${where}.number`);
  httpsUrl(row.url, `${where}.url`);
  lineText(row.title, `${where}.title`);
  enumValue(row.state, CHANGE_REQUEST_STATES, `${where}.state`);
  require(typeof row.draft === "boolean", `${where}.draft: boolean required`);
  require("author" in row, `${where}.author: required`);
  validateNullableActor(row.author, `${where}.author`);
  lineText(row.base_label, `${where}.base_label`);
  lineText(row.head_label, `${where}.head_label`);
  const created = Date.parse(timestamp(row.created_at, `${where}.created_at`));
  const updated = Date.parse(timestamp(row.updated_at, `${where}.updated_at`));
  require(updated >= created, `${where}.updated_at precedes created_at`);
  return row;
}

/** @param {unknown} raw @returns {ParseResult} */
export function parseChangeRequestIndex(raw) {
  return parseRecord(raw, "change_request_index", (document) => {
    forbidExtras(document, ["query_key", "query", "rows"], "change_request_index");
    const queryKey = sha256Digest(document.query_key, "change_request_index.query_key");
    const query = validateChangeRequestIndexQuery(document.query, "change_request_index.query");
    require(queryKey ===
      changeRequestIndexQueryKey(query), "change_request_index.query_key: does not match query");
    const rows = asArray(document.rows, "change_request_index.rows");
    const queryRepository = asObject(query.repository, "change_request_index.query.repository");
    const stateFilter = asObject(query.state_filter, "change_request_index.query.state_filter");
    const selectedStates =
      stateFilter.kind === "selected"
        ? new Set(asArray(stateFilter.states, "change_request_index.query.state_filter.states"))
        : null;
    const sort = asObject(query.sort, "change_request_index.query.sort");
    const bounds = asObject(query.bounds, "change_request_index.query.bounds");
    const seen = new Set();
    let previous = null;
    for (const [index, rawRow] of rows.entries()) {
      const row = validateChangeRequestIndexRow(rawRow, `change_request_index.rows[${index}]`);
      require(sameRepositoryRef(
        row.repository,
        queryRepository,
      ), `change_request_index.rows[${index}]: repository does not match query`);
      const provider = asObject(
        row.provider_ref,
        `change_request_index.rows[${index}].provider_ref`,
      );
      const opaqueId = nonemptyString(
        provider.opaque_id,
        `change_request_index.rows[${index}].provider_ref.opaque_id`,
      );
      utf8Bytes(opaqueId, `change_request_index.rows[${index}].provider_ref.opaque_id`);
      require(!seen.has(opaqueId), "change_request_index.rows: duplicate provider opaque ID");
      seen.add(opaqueId);
      require(selectedStates === null ||
        selectedStates.has(
          row.state,
        ), `change_request_index.rows[${index}]: state does not match query`);
      if (previous !== null) {
        const previousProvider = asObject(previous.provider_ref, "previous.provider_ref");
        const previousPrimary = Date.parse(String(previous[String(sort.field)]));
        const currentPrimary = Date.parse(String(row[String(sort.field)]));
        const primaryOrder =
          sort.direction === "ascending"
            ? currentPrimary - previousPrimary
            : previousPrimary - currentPrimary;
        require(primaryOrder > 0 ||
          (primaryOrder === 0 &&
            compareUtf8(opaqueId, String(previousProvider.opaque_id)) >
              0), "change_request_index.rows: declared deterministic order violated");
      }
      previous = row;
    }
    require(rows.length <=
      Number(bounds.max_items), "change_request_index.rows: item bound exceeded");
  });
}

/** @param {unknown} raw @returns {ParseResult} */
export function parseChangeRequestComment(raw) {
  return parseRecord(raw, "change_request_comment", (document) => {
    forbidExtras(
      document,
      [
        "id",
        "provider_ref",
        "repository",
        "change_request_id",
        "url",
        "author",
        "state",
        "created_at",
        "updated_at",
      ],
      "change_request_comment",
    );
    validateHostedIdentity(document, "change_request_comment");
    domainId(document.change_request_id, "change_request_comment.change_request_id");
    require("author" in document, "change_request_comment.author: required");
    validateNullableActor(document.author, "change_request_comment.author");
    validateCommentLifecycle(document, "change_request_comment");
  });
}

/** @param {unknown} raw @returns {ParseResult} */
export function parseReview(raw) {
  return parseRecord(raw, "review", (document) => {
    forbidExtras(
      document,
      [
        "id",
        "provider_ref",
        "repository",
        "change_request_id",
        "url",
        "author",
        "disposition",
        "revision",
        "created_at",
        "submitted_at",
        "updated_at",
      ],
      "review",
    );
    validateHostedIdentity(document, "review");
    domainId(document.change_request_id, "review.change_request_id");
    httpsUrl(document.url, "review.url");
    require("author" in document, "review.author: required");
    validateNullableActor(document.author, "review.author");
    const disposition = enumValue(document.disposition, REVIEW_DISPOSITIONS, "review.disposition");
    validateGitObjectRef(document.revision, "review.revision");
    const revision = asObject(document.revision, "review.revision");
    require(revision.observation !== "not_requested", "review.revision: must be requested");
    const created = Date.parse(timestamp(document.created_at, "review.created_at"));
    const updated = Date.parse(timestamp(document.updated_at, "review.updated_at"));
    require(updated >= created, "review.updated_at precedes created_at");
    require("submitted_at" in document, "review.submitted_at: required");
    validateNullableTimestamp(document.submitted_at, "review.submitted_at");
    if (disposition === "pending") {
      require(document.submitted_at === null, "review.pending: submitted_at is forbidden");
    } else if (disposition !== "unknown") {
      require(document.submitted_at !==
        null, "review: submitted disposition requires submitted_at");
    }
    if (document.submitted_at !== null) {
      const submitted = Date.parse(String(document.submitted_at));
      require(submitted >= created &&
        submitted <= updated, "review.submitted_at falls outside lifecycle");
    }
  });
}

/** @param {unknown} raw @returns {ParseResult} */
export function parseReviewThread(raw) {
  return parseRecord(raw, "review_thread", (document) => {
    forbidExtras(
      document,
      [
        "id",
        "provider_ref",
        "repository",
        "change_request_id",
        "anchor",
        "state",
        "resolved_by",
        "comment_count",
      ],
      "review_thread",
    );
    validateHostedIdentity(document, "review_thread");
    domainId(document.change_request_id, "review_thread.change_request_id");
    validateReviewAnchor(document.anchor, "review_thread.anchor");
    const state = enumValue(document.state, REVIEW_THREAD_STATES, "review_thread.state");
    require("resolved_by" in document, "review_thread.resolved_by: required");
    validateNullableActor(document.resolved_by, "review_thread.resolved_by");
    require(document.resolved_by === null ||
      state === "resolved", "review_thread.resolved_by: allowed only for resolved threads");
    nonnegativeInteger(document.comment_count, "review_thread.comment_count");
  });
}

/** @param {unknown} raw @returns {ParseResult} */
export function parseReviewComment(raw) {
  return parseRecord(raw, "review_comment", (document) => {
    forbidExtras(
      document,
      [
        "id",
        "provider_ref",
        "repository",
        "change_request_id",
        "review_id",
        "thread_id",
        "in_reply_to_id",
        "url",
        "author",
        "state",
        "anchor",
        "created_at",
        "updated_at",
      ],
      "review_comment",
    );
    validateHostedIdentity(document, "review_comment");
    domainId(document.change_request_id, "review_comment.change_request_id");
    require("review_id" in document, "review_comment.review_id: required");
    if (document.review_id !== null) {
      domainId(document.review_id, "review_comment.review_id");
    }
    domainId(document.thread_id, "review_comment.thread_id");
    require("in_reply_to_id" in document, "review_comment.in_reply_to_id: required");
    if (document.in_reply_to_id !== null) {
      domainId(document.in_reply_to_id, "review_comment.in_reply_to_id");
    }
    require(document.in_reply_to_id !== document.id, "review_comment: cannot reply to itself");
    require("author" in document, "review_comment.author: required");
    validateNullableActor(document.author, "review_comment.author");
    validateReviewAnchor(document.anchor, "review_comment.anchor");
    validateCommentLifecycle(document, "review_comment");
  });
}

/** @param {unknown} raw @returns {ParseResult} */
export function parseCheck(raw) {
  return parseRecord(raw, "check", (document) => {
    forbidExtras(
      document,
      [
        "id",
        "provider_ref",
        "repository",
        "parent_check_id",
        "kind",
        "revision",
        "name",
        "status",
        "conclusion",
        "url",
        "started_at",
        "completed_at",
      ],
      "check",
    );
    validateHostedIdentity(document, "check");
    require("parent_check_id" in document, "check.parent_check_id: required");
    if (document.parent_check_id !== null) {
      domainId(document.parent_check_id, "check.parent_check_id");
    }
    const kind = enumValue(document.kind, CHECK_KINDS, "check.kind");
    validateGitObjectRef(document.revision, "check.revision");
    const revision = asObject(document.revision, "check.revision");
    require(revision.observation === "observed", "check.revision: observed revision required");
    require(document.parent_check_id !== document.id, "check: cannot parent itself");
    require("name" in document, "check.name: required");
    if (document.name !== null) {
      lineText(document.name, "check.name");
    }
    if (kind === "run") {
      require(document.parent_check_id !== null, "check run: parent suite required");
      require(document.name !== null, "check run: name required");
    } else if (kind === "suite") {
      require(document.parent_check_id === null, "check suite: parent forbidden");
    }
    const status = enumValue(document.status, CHECK_STATUSES, "check.status");
    require("conclusion" in document, "check.conclusion: required");
    if (document.conclusion !== null) {
      enumValue(document.conclusion, CHECK_CONCLUSIONS, "check.conclusion");
    }
    require("url" in document, "check.url: required");
    validateNullableUrl(document.url, "check.url");
    require("started_at" in document, "check.started_at: required");
    validateNullableTimestamp(document.started_at, "check.started_at");
    require("completed_at" in document, "check.completed_at: required");
    validateNullableTimestamp(document.completed_at, "check.completed_at");
    if (status === "completed") {
      require(document.conclusion !== null, "completed check: conclusion required");
      require(kind !== "run" ||
        document.completed_at !== null, "completed check run: completed_at required");
    } else {
      require(document.conclusion === null &&
        document.completed_at ===
          null, "noncompleted check: conclusion and completed_at forbidden");
    }
    if (document.started_at !== null && document.completed_at !== null) {
      require(Date.parse(String(document.completed_at)) >=
        Date.parse(String(document.started_at)), "check.completed_at precedes started_at");
    }
  });
}

/** @param {unknown} raw @returns {ParseResult} */
export function parseCommitStatus(raw) {
  return parseRecord(raw, "commit_status", (document) => {
    forbidExtras(
      document,
      [
        "id",
        "provider_ref",
        "repository",
        "revision",
        "context",
        "state",
        "description",
        "target_url",
        "created_at",
        "updated_at",
      ],
      "commit_status",
    );
    validateHostedIdentity(document, "commit_status");
    validateGitObjectRef(document.revision, "commit_status.revision");
    const revision = asObject(document.revision, "commit_status.revision");
    require(revision.observation === "observed", "commit_status.revision: observed required");
    lineText(document.context, "commit_status.context");
    enumValue(document.state, COMMIT_STATUS_STATES, "commit_status.state");
    require("description" in document, "commit_status.description: required");
    if (document.description !== null) {
      lineText(document.description, "commit_status.description");
    }
    require("target_url" in document, "commit_status.target_url: required");
    validateNullableUrl(document.target_url, "commit_status.target_url");
    const created = Date.parse(timestamp(document.created_at, "commit_status.created_at"));
    const updated = Date.parse(timestamp(document.updated_at, "commit_status.updated_at"));
    require(updated >= created, "commit_status.updated_at precedes created_at");
  });
}

/** @param {unknown} raw @param {string} where @returns {Record<string, unknown>} */
function validateActivityActor(raw, where) {
  const actor = asObject(raw, where);
  const kind = nonemptyString(actor.kind, `${where}.kind`);
  if (kind === "git") {
    forbidExtras(actor, ["kind", "name", "email"], where);
    lineText(actor.name, `${where}.name`);
    require("email" in actor, `${where}.email: required`);
    if (actor.email !== null) {
      lineText(actor.email, `${where}.email`);
    }
  } else if (kind === "provider") {
    forbidExtras(actor, ["kind", "actor"], where);
    validateActorRef(actor.actor, `${where}.actor`);
  } else {
    throw new FormatError(`${where}.kind: unknown value`);
  }
  return actor;
}

/** @param {unknown} raw @param {string} where @returns {Record<string, unknown>} */
function validateActivityDetail(raw, where) {
  const detail = asObject(raw, where);
  const kind = nonemptyString(detail.kind, `${where}.kind`);
  if (kind === "commit") {
    forbidExtras(detail, ["kind", "revision"], where);
    validateGitObjectRef(detail.revision, `${where}.revision`);
  } else if (kind === "change_request") {
    forbidExtras(
      detail,
      ["kind", "change_request_id", "provider_ref", "repository", "number"],
      where,
    );
    domainId(detail.change_request_id, `${where}.change_request_id`);
    validateProviderObjectRef(detail.provider_ref, `${where}.provider_ref`);
    validateRepositoryRef(detail.repository, `${where}.repository`);
    requireSameProviderInstance(
      asObject(detail.provider_ref, `${where}.provider_ref`),
      asObject(detail.repository, `${where}.repository`),
      where,
    );
    positiveInteger(detail.number, `${where}.number`);
  } else {
    throw new FormatError(`${where}.kind: unknown value`);
  }
  return detail;
}

/** @param {unknown} raw @param {string} where @returns {Record<string, unknown>} */
function validateActivityFreshness(raw, where) {
  const freshness = asObject(raw, where);
  const kind = nonemptyString(freshness.kind, `${where}.kind`);
  if (kind === "immutable") {
    forbidExtras(freshness, ["kind"], where);
  } else if (kind === "observed") {
    forbidExtras(freshness, ["kind", "snapshot_id", "observed_at"], where);
    sha256Digest(freshness.snapshot_id, `${where}.snapshot_id`);
    timestamp(freshness.observed_at, `${where}.observed_at`);
  } else {
    throw new FormatError(`${where}.kind: unknown value`);
  }
  return freshness;
}

/** @param {unknown} raw @param {string} where @returns {Record<string, unknown>} */
function validateActivityItem(raw, where) {
  const item = asObject(raw, where);
  forbidExtras(
    item,
    [
      "id",
      "kind",
      "title",
      "actors",
      "event_at",
      "updated_at",
      "state",
      "primary_revision",
      "base_revision",
      "head_revision",
      "comparison_observed",
      "detail",
      "freshness",
    ],
    where,
  );
  domainId(item.id, `${where}.id`);
  const kind = enumValue(item.kind, ACTIVITY_KINDS, `${where}.kind`);
  lineText(item.title, `${where}.title`);
  const actors = asArray(item.actors, `${where}.actors`).map((actor, index) =>
    validateActivityActor(actor, `${where}.actors[${index}]`),
  );
  const eventAt = Date.parse(timestamp(item.event_at, `${where}.event_at`));
  const updatedAt = Date.parse(timestamp(item.updated_at, `${where}.updated_at`));
  require(updatedAt >= eventAt, `${where}.updated_at precedes event_at`);
  require("state" in item, `${where}.state: required`);
  if (item.state !== null) {
    enumValue(item.state, ACTIVITY_STATES, `${where}.state`);
  }
  validateRevisionRef(item.primary_revision, `${where}.primary_revision`);
  require("base_revision" in item, `${where}.base_revision: required`);
  if (item.base_revision !== null) {
    validateRevisionRef(item.base_revision, `${where}.base_revision`);
  }
  require("head_revision" in item, `${where}.head_revision: required`);
  if (item.head_revision !== null) {
    validateRevisionRef(item.head_revision, `${where}.head_revision`);
  }
  require(typeof item.comparison_observed ===
    "boolean", `${where}.comparison_observed: boolean required`);
  const detail = validateActivityDetail(item.detail, `${where}.detail`);
  const freshness = validateActivityFreshness(item.freshness, `${where}.freshness`);
  const primary = asObject(item.primary_revision, `${where}.primary_revision`);

  if (kind === "commit") {
    require(item.state === null, `${where}: commit state is forbidden`);
    require(detail.kind === "commit" &&
      freshness.kind === "immutable", `${where}: commit detail and freshness required`);
    require(item.base_revision === null &&
      item.head_revision === null, `${where}: commit comparison revisions are forbidden`);
    require(item.comparison_observed ===
      false, `${where}: commit cannot claim an observed comparison`);
    require(actors.every((actor) => actor.kind === "git"), `${where}: commit requires Git actors`);
    const detailRevision = asObject(detail.revision, `${where}.detail.revision`);
    require(primary.observation === "observed" &&
      detailRevision.repository_id === primary.repository_id &&
      detailRevision.oid ===
        primary.oid, `${where}: commit detail must identify the observed primary revision`);
    return item;
  }

  require(item.state !== null, `${where}: change-request state required`);
  require(actors.every(
    (actor) => actor.kind === "provider",
  ), `${where}: change request requires provider actors`);
  require(detail.kind === "change_request" &&
    freshness.kind === "observed", `${where}: change-request detail and freshness required`);
  require(item.base_revision !== null &&
    item.head_revision !== null, `${where}: change-request comparison revisions required`);
  const base = asObject(item.base_revision, `${where}.base_revision`);
  const head = asObject(item.head_revision, `${where}.head_revision`);
  const detailRepository = asObject(detail.repository, `${where}.detail.repository`);
  require(base.repository_id ===
    detailRepository.opaque_id, `${where}: base revision must belong to hosted repository`);
  require(sameRevisionRef(
    item.primary_revision,
    item.head_revision,
  ), `${where}: primary revision must be the head revision`);
  const revisionsObserved = base.observation === "observed" && head.observation === "observed";
  require(item.comparison_observed ===
    revisionsObserved, `${where}: comparison_observed disagrees with revision observations`);
  return item;
}

/** @param {unknown} raw @param {string} where @returns {Record<string, unknown>} */
function validateOpaqueContinuation(raw, where) {
  const continuation = asObject(raw, where);
  forbidExtras(continuation, ["kind", "value"], where);
  require(continuation.kind === "opaque_cursor", `${where}.kind: opaque_cursor required`);
  const value = nonemptyString(continuation.value, `${where}.value`);
  require(value.length <= MAX_OPAQUE_CURSOR_LENGTH &&
    OPAQUE_CURSOR_RE.test(value) &&
    !URI_SCHEME_RE.test(value), `${where}.value: bounded URL-free cursor required`);
  return continuation;
}

/** @param {unknown} raw @param {string} where @returns {Record<string, unknown>} */
function validateTruncation(raw, where) {
  const truncation = asObject(raw, where);
  forbidExtras(truncation, ["reason", "limit"], where);
  const reason = enumValue(truncation.reason, TRUNCATION_REASONS, `${where}.reason`);
  require("limit" in truncation, `${where}.limit: required`);
  if (truncation.limit !== null) {
    positiveInteger(truncation.limit, `${where}.limit`);
  }
  require((truncation.limit !== null) ===
    BOUNDED_TRUNCATION_REASONS.has(
      reason,
    ), `${where}: bounded reasons require exactly one positive limit`);
  return truncation;
}

/** @param {unknown} raw @returns {ParseResult} */
export function parseRepositoryActivity(raw) {
  return parseRecord(raw, "repository_activity", (document) => {
    forbidExtras(
      document,
      [
        "repository_id",
        "included_kinds",
        "max_items",
        "order",
        "coverage",
        "items",
        "continuation",
        "truncation",
      ],
      "repository_activity",
    );
    const repositoryId = providerId(document.repository_id, "repository_activity.repository_id");
    const includedKinds = asArray(document.included_kinds, "repository_activity.included_kinds");
    require(includedKinds.length > 0, "repository_activity.included_kinds: nonempty required");
    let previousKind = null;
    for (const [index, rawKind] of includedKinds.entries()) {
      const kind = enumValue(
        rawKind,
        ACTIVITY_KINDS,
        `repository_activity.included_kinds[${index}]`,
      );
      require(previousKind === null ||
        kind > previousKind, "repository_activity.included_kinds: sorted unique values required");
      previousKind = kind;
    }
    const maxItems = Number(document.max_items);
    positiveInteger(document.max_items, "repository_activity.max_items");
    require(document.order ===
      "event_at_desc_id_asc", "repository_activity.order: event_at_desc_id_asc required");
    const coverage = enumValue(
      document.coverage,
      ACTIVITY_COVERAGE,
      "repository_activity.coverage",
    );
    const items = asArray(document.items, "repository_activity.items").map((item, index) =>
      validateActivityItem(item, `repository_activity.items[${index}]`),
    );
    require(items.length <= maxItems, "repository_activity.items: max_items exceeded");
    const included = new Set(includedKinds);
    const seen = new Set();
    let previousItem = null;
    for (const item of items) {
      const id = String(item.id);
      require(!seen.has(id), "repository_activity.items: duplicate ID");
      seen.add(id);
      require(included.has(item.kind), "repository_activity.items: undeclared kind");
      if (item.kind === "commit") {
        const primary = asObject(item.primary_revision, "activity.primary_revision");
        require(primary.repository_id ===
          repositoryId, "repository_activity: commit belongs to another repository");
      }
      if (previousItem !== null) {
        const previousTime = Date.parse(String(previousItem.event_at));
        const currentTime = Date.parse(String(item.event_at));
        require(currentTime < previousTime ||
          (currentTime === previousTime &&
            compareUtf8(id, String(previousItem.id)) >
              0), "repository_activity.items: deterministic order violated");
      }
      previousItem = item;
    }
    require("continuation" in document, "repository_activity.continuation: required");
    if (document.continuation !== null) {
      validateOpaqueContinuation(document.continuation, "repository_activity.continuation");
    }
    require("truncation" in document, "repository_activity.truncation: required");
    const truncation =
      document.truncation === null
        ? null
        : validateTruncation(document.truncation, "repository_activity.truncation");
    if (coverage === "complete") {
      require(document.continuation === null &&
        truncation ===
          null, "repository_activity: complete coverage forbids continuation and truncation");
    } else {
      require(truncation !== null, "repository_activity: partial coverage requires truncation");
      if (truncation !== null && truncation.reason === "item_bound") {
        require(truncation.limit === maxItems &&
          items.length ===
            maxItems, "repository_activity: item-bound truncation must reach max_items");
      }
    }
  });
}
