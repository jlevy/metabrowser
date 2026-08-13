export const OTHER_KEY = "";

/** @param {string} key */
export function hashKey(key) {
  let hash = 2166136261;
  for (let index = 0; index < key.length; index += 1) {
    hash ^= key.charCodeAt(index);
    hash = Math.imul(hash, 16777619);
  }
  return hash >>> 0;
}

/** @param {{assignments: Map<string, number>, reserved: Set<number>}} session @param {string} key @param {number} slotCount */
export function assignSlot(session, key, slotCount) {
  const existing = session.assignments.get(key);
  if (existing !== undefined) {
    return existing;
  }
  const start = hashKey(key) % slotCount;
  for (let offset = 0; offset < slotCount; offset += 1) {
    const slot = ((start + offset) % slotCount) + 1;
    if (!session.reserved.has(slot)) {
      session.reserved.add(slot);
      session.assignments.set(key, slot);
      return slot;
    }
  }
  const fallback = start + 1;
  session.assignments.set(key, fallback);
  return fallback;
}

/** @param {number} slotCount */
export function createCategoryPalettePool(slotCount) {
  if (!Number.isInteger(slotCount) || slotCount < 1) {
    throw new TypeError("palette slot count must be a positive integer");
  }
  /** @type {Map<string, {assignments: Map<string, number>, reserved: Set<number>, refs: number}>} */
  const sessions = new Map();
  return Object.freeze({
    /** @param {string} path */
    acquire(path) {
      let session = sessions.get(path);
      if (!session) {
        session = { assignments: new Map(), reserved: new Set(), refs: 0 };
        sessions.set(path, session);
      }
      session.refs += 1;
      let released = false;
      return Object.freeze({
        /** @param {Array<string>} keys */
        sync(keys) {
          for (const key of keys) {
            if (key !== OTHER_KEY) {
              assignSlot(session, key, slotCount);
            }
          }
        },
        /** @param {string} key */
        slotFor(key) {
          return key === OTHER_KEY ? 0 : assignSlot(session, key, slotCount);
        },
        /** @param {string} key */
        classFor(key) {
          return key === OTHER_KEY
            ? "mb-distribution-other"
            : `mb-distribution-slot-${assignSlot(session, key, slotCount)}`;
        },
        release() {
          if (released) {
            return;
          }
          released = true;
          session.refs -= 1;
          if (session.refs === 0) {
            sessions.delete(path);
          }
        },
      });
    },
  });
}
