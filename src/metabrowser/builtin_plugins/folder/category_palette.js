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

/** @param {{assignments: Map<string, number>, reserved: Set<number>, consumers: Map<number, Set<string>>}} session @param {number} slotCount */
function reconcileSession(session, slotCount) {
  const liveKeys = new Set();
  for (const consumerKeys of session.consumers.values()) {
    for (const key of consumerKeys) {
      liveKeys.add(key);
    }
  }
  for (const key of session.assignments.keys()) {
    if (!liveKeys.has(key)) {
      session.assignments.delete(key);
    }
  }
  session.reserved.clear();
  for (const slot of session.assignments.values()) {
    session.reserved.add(slot);
  }
  for (const key of liveKeys) {
    assignSlot(session, key, slotCount);
  }
}

/** @param {number} slotCount */
export function createCategoryPalettePool(slotCount) {
  if (!Number.isInteger(slotCount) || slotCount < 1) {
    throw new TypeError("palette slot count must be a positive integer");
  }
  /** @type {Map<string, {assignments: Map<string, number>, reserved: Set<number>, consumers: Map<number, Set<string>>, refs: number}>} */
  const sessions = new Map();
  let consumerSequence = 0;
  return Object.freeze({
    /** @param {string} path */
    acquire(path) {
      let session = sessions.get(path);
      if (!session) {
        session = { assignments: new Map(), reserved: new Set(), consumers: new Map(), refs: 0 };
        sessions.set(path, session);
      }
      session.refs += 1;
      const consumerId = ++consumerSequence;
      session.consumers.set(consumerId, new Set());
      let released = false;
      return Object.freeze({
        /** @param {Array<string>} keys */
        sync(keys) {
          session.consumers.set(consumerId, new Set(keys.filter((key) => key !== OTHER_KEY)));
          reconcileSession(session, slotCount);
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
          session.consumers.delete(consumerId);
          if (session.refs === 0) {
            sessions.delete(path);
          } else {
            reconcileSession(session, slotCount);
          }
        },
      });
    },
  });
}
