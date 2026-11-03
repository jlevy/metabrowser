// Raw Chrome DevTools Protocol over Node built-in WebSocket; no dependencies.
export const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
export const CHROME =
  process.env.CHROME_BIN || "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";

export class Connection {
  constructor(url) {
    this.url = url;
    this.id = 0;
    this.pending = new Map();
    this.sessions = new Map(); // sessionId -> Session
    this.listeners = new Set();
  }
  open() {
    return new Promise((resolve, reject) => {
      this.ws = new WebSocket(this.url);
      this.ws.onopen = () => resolve();
      this.ws.onerror = (e) => reject(new Error(`websocket error: ${e.message || e.type}`));
      this.ws.onmessage = (m) => this._onMessage(JSON.parse(m.data));
      this.ws.onclose = () => {
        for (const [, p] of this.pending) {
          p.reject(new Error("connection closed"));
        }
        this.pending.clear();
      };
    });
  }
  close() {
    try {
      this.ws.close();
    } catch {}
  }
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
      const payload = { id, method, params };
      if (sessionId) {
        payload.sessionId = sessionId;
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
  adopt(sessionId, targetId) {
    const s = new Session(this, sessionId, targetId);
    this.sessions.set(sessionId, s);
    return s;
  }
}

export class Session {
  constructor(conn, sessionId, targetId) {
    this.conn = conn;
    this.sessionId = sessionId;
    this.targetId = targetId;
    this.handlers = new Map();
  }
  send(method, params = {}, timeoutMs = 60000) {
    return this.conn.send(method, params, this.sessionId, timeoutMs);
  }
  on(method, fn) {
    if (!this.handlers.has(method)) {
      this.handlers.set(method, new Set());
    }
    this.handlers.get(method).add(fn);
    return () => this.handlers.get(method).delete(fn);
  }
  _dispatch(method, params) {
    const set = this.handlers.get(method);
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
