// The GitPath wire codec: a pinned revision's path as `/view/` addresses it, and back.
//
// A pin's tree holds names that are not valid inventory paths, or not UTF-8 at all, so
// its addresses carry each segment as `g1-` and unpadded base64url. Only a pinned
// revision's page reads or writes that spelling, and it needs it before its first
// paint, so the server writes this script into a pin's shell, ahead of navigation.js,
// and leaves it out of a folder's, as it does the pin guard.
//
// Measured 2026-10-01: in navigation.js this was 885 compressed bytes of a startup
// script on every folder's page. See
// explorations/performance-loop/experiments/exp-037.

(() => {
  /** @param {string} token */
  function isGitPathToken(token) {
    return token.startsWith("g1-") && token.length > 3;
  }

  /**
   * The GitPath wire of a slash-separated path on a pinned revision, as `/view/`
   * addresses it: `g1-` and the unpadded base64url of each segment's bytes. A string is
   * its UTF-8 bytes; a name that is not UTF-8 is given as its bytes, since its display
   * spelling holds replacement characters. Null for a path with no segment or an empty
   * one, which no tree entry has.
   *
   * @param {string | Uint8Array} path
   * @returns {string | null}
   */
  function gitPathWire(path) {
    const bytes = typeof path === "string" ? new TextEncoder().encode(path) : path;
    const tokens = [];
    let start = 0;
    for (let index = 0; index <= bytes.length; index += 1) {
      if (index < bytes.length && bytes[index] !== 0x2f) {
        continue;
      }
      if (index === start) {
        return null;
      }
      let binary = "";
      for (let at = start; at < index; at += 1) {
        binary += String.fromCharCode(bytes[at]);
      }
      tokens.push(
        `g1-${btoa(binary).replaceAll("+", "-").replaceAll("/", "_").replace(/=+$/, "")}`,
      );
      start = index + 1;
    }
    return tokens.join("/");
  }

  /** Canonical unpadded base64url atom to replacement-safe UTF-8, or null.
   * @param {string} atom
   */
  function decodeGitPathAtom(atom) {
    if (!atom || /[^A-Za-z0-9_-]/.test(atom)) {
      return null;
    }
    const padded = atom + "=".repeat((4 - (atom.length % 4)) % 4);
    let binary;
    try {
      binary = atob(padded.replaceAll("-", "+").replaceAll("_", "/"));
    } catch (_error) {
      return null;
    }
    let encoded;
    try {
      encoded = btoa(binary).replaceAll("+", "-").replaceAll("/", "_").replace(/=+$/, "");
    } catch (_error) {
      return null;
    }
    if (encoded !== atom) {
      return null;
    }
    const bytes = new Uint8Array(binary.length);
    for (let i = 0; i < binary.length; i += 1) {
      bytes[i] = binary.charCodeAt(i);
    }
    const text = new TextDecoder("utf-8").decode(bytes);
    if (!text || text.includes("\0") || text.includes("/")) {
      return null;
    }
    let sanitized = "";
    for (const ch of text) {
      const code = ch.charCodeAt(0);
      sanitized += code < 32 || code === 127 ? "\uFFFD" : ch;
    }
    return sanitized;
  }

  /** Decode a contiguous GitPath wire prefix. Null when this is not a GitPath identity.
   * @param {string} path
   */
  function displayGitPathWire(path) {
    const parts = path.split("/");
    let cut = 0;
    while (cut < parts.length && isGitPathToken(parts[cut])) {
      cut += 1;
    }
    if (cut === 0) {
      return null;
    }
    const decoded = [];
    for (let i = 0; i < cut; i += 1) {
      const segment = decodeGitPathAtom(parts[i].slice(3));
      if (segment === null) {
        return null;
      }
      decoded.push(segment);
    }
    const gitDisplay = decoded.join("/");
    if (cut === parts.length) {
      return gitDisplay;
    }
    return `${gitDisplay}/${parts.slice(cut).join("/").replaceAll("%25", "%")}`;
  }

  window.MetabrowserGitPath = Object.freeze({
    display: displayGitPathWire,
    wire: gitPathWire,
  });
})();
