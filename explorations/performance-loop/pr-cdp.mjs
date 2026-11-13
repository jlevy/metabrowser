// Raw Chrome DevTools Protocol over Node built-in WebSocket; no dependencies.
// Typed with JSDoc for apps/macos/webkit-gate/tsconfig.json, which checks the gate that
// imports it. Protocol params and results are untyped JSON, so they stay `any`.

/**
 * @typedef {{ message: string, data?: string }} CdpError
 * @typedef {{
 *   id?: number, method?: string, params?: any, result?: any, error?: CdpError,
 *   sessionId?: string
 * }} CdpMessage
 * @typedef {{ method: string, resolve: (value: any) => void, reject: (error: Error) => void }} Pending
 * @typedef {(...args: any[]) => void} Handler
 */

/** @param {number} ms */
export const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
export const CHROME =
  process.env.CHROME_BIN || "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";

export class Connection {
  /** @param {string} url */
  constructor(url) {
    this.url = url;
    this.id = 0;
    /** @type {Map<number, Pending>} */
    this.pending = new Map();
    /** @type {Map<string, Session>} sessionId -> Session */
    this.sessions = new Map();
    /** @type {Set<(method: string | undefined, params: any, sessionId: string | undefined) => void>} */
    this.listeners = new Set();
    /** @type {WebSocket | undefined} */
    this.ws = undefined;
  }
  /** @returns {Promise<void>} */
  open() {
    return new Promise((resolve, reject) => {
      const ws = new WebSocket(this.url);
      this.ws = ws;
      ws.onopen = () => resolve();
      ws.onerror = (e) =>
        reject(new Error(`websocket error: ${/** @type {any} */ (e).message || e.type}`));
      ws.onmessage = (m) => this._onMessage(JSON.parse(m.data));
      ws.onclose = () => {
        for (const [, p] of this.pending) {
          p.reject(new Error("connection closed"));
        }
        this.pending.clear();
      };
    });
  }
  close() {
    try {
      this.ws?.close();
    } catch {}
  }
  /** @param {CdpMessage} msg */
  _onMessage(msg) {
    if (msg.id !== undefined) {
      const p = this.pending.get(msg.id);
      if (!p) {
        return;
      }
      this.pending.delete(msg.id);
      if (msg.error) {
        p.reject(
          new Error(
            `${p.method}: ${msg.error.message}${msg.error.data ? ` (${msg.error.data})` : ""}`,
          ),
        );
      } else {
        p.resolve(msg.result);
      }
      return;
    }
    if (msg.sessionId) {
      const s = this.sessions.get(msg.sessionId);
      if (s) {
        s._dispatch(msg.method, msg.params);
      }
    }
    for (const l of this.listeners) {
      l(msg.method, msg.params, msg.sessionId);
    }
  }
  /**
   * @param {string} method
   * @param {object} [params]
   * @param {string} [sessionId]
   * @param {number} [timeoutMs]
   * @returns {Promise<any>}
   */
  send(method, params = {}, sessionId = undefined, timeoutMs = 60000) {
    return new Promise((resolve, reject) => {
      const id = ++this.id;
      const timer = setTimeout(() => {
        if (this.pending.delete(id)) {
          reject(new Error(`${method}: no reply in ${timeoutMs} ms`));
        }
      }, timeoutMs);
      this.pending.set(id, {
        method,
        resolve: (v) => {
          clearTimeout(timer);
          resolve(v);
        },
        reject: (e) => {
          clearTimeout(timer);
          reject(e);
        },
      });
      /** @type {CdpMessage} */
      const payload = { id, method, params };
      if (sessionId) {
        payload.sessionId = sessionId;
      }
      if (!this.ws) {
        throw new Error(`${method}: the connection is not open`);
      }
      this.ws.send(JSON.stringify(payload));
    });
  }
  async newPage(url = "about:blank") {
    const { targetId } = await this.send("Target.createTarget", { url });
    const { sessionId } = await this.send("Target.attachToTarget", { targetId, flatten: true });
    const s = new Session(this, sessionId, targetId);
    this.sessions.set(sessionId, s);
    return s;
  }
  /**
   * @param {string} sessionId
   * @param {string} targetId
   */
  adopt(sessionId, targetId) {
    const s = new Session(this, sessionId, targetId);
    this.sessions.set(sessionId, s);
    return s;
  }
}

export class Session {
  /**
   * @param {Connection} conn
   * @param {string} sessionId
   * @param {string} targetId
   */
  constructor(conn, sessionId, targetId) {
    this.conn = conn;
    this.sessionId = sessionId;
    this.targetId = targetId;
    /** @type {Map<string, Set<Handler>>} */
    this.handlers = new Map();
  }
  /**
   * @param {string} method
   * @param {object} [params]
   * @param {number} [timeoutMs]
   */
  send(method, params = {}, timeoutMs = 60000) {
    return this.conn.send(method, params, this.sessionId, timeoutMs);
  }
  /**
   * @param {string} method
   * @param {Handler} fn
   */
  on(method, fn) {
    let set = this.handlers.get(method);
    if (!set) {
      set = new Set();
      this.handlers.set(method, set);
    }
    set.add(fn);
    return () => this.handlers.get(method)?.delete(fn);
  }
  /**
   * @param {string | undefined} method
   * @param {any} params
   */
  _dispatch(method, params) {
    const set = method === undefined ? undefined : this.handlers.get(method);
    if (set) {
      for (const fn of [...set]) {
        fn(params);
      }
    }
    const any = this.handlers.get("*");
    if (any) {
      for (const fn of [...any]) {
        fn(method, params);
      }
    }
  }
  /**
   * @param {string} method
   * @param {(params: any) => boolean} [predicate]
   * @param {number} [timeoutMs]
   * @returns {Promise<any>}
   */
  once(method, predicate = () => true, timeoutMs = 30000) {
    return new Promise((resolve, reject) => {
      const timer = setTimeout(() => {
        off();
        reject(new Error(`timed out waiting for ${method}`));
      }, timeoutMs);
      const off = this.on(method, (params) => {
        if (!predicate(params)) {
          return;
        }
        clearTimeout(timer);
        off();
        resolve(params);
      });
    });
  }
  async close() {
    try {
      await this.conn.send("Target.closeTarget", { targetId: this.targetId });
    } catch {}
    this.conn.sessions.delete(this.sessionId);
  }
}
