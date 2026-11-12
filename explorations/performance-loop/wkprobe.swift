// WKWebView measurement probe for the Metabrowser performance loop.
//
// One process drives one real WKWebView through the steps of a job and writes what it
// saw as JSON. `wkprobe.mjs` compiles this file with swiftc, starts the server and the
// logging proxy, and runs the jobs; see README.md, "WKWebView Probe". Nothing here is
// product code, and there is no Xcode project, bundle, or signing: the wrapper embeds
// an Info.plist in the executable so WebKit files its data under one known identifier.
//
//   mb-wkprobe JOB_JSON
//
// A job names the page origin (the logging proxy), the path and subject to load, the
// website data store (`ephemeral`, a UUID for a persistent store, or `remove:UUID`),
// the window mode (`visible`, or `hidden`: created but never ordered in), and its steps:
//   load              load the path and wait for the exact subject to be ready
//   reload            WKWebView.reload() and wait again
//   hidden-load-show  load while hidden, record the hidden first view, then show the
//                     window and time show-to-ready
// Every step is bracketed by GET /__mark requests to the proxy, so the wrapper can
// attribute each logged request to its step.
import AppKit
import CoreGraphics
import WebKit

func nowMs() -> Double { ProcessInfo.processInfo.systemUptime * 1000 }
let processStart = nowMs()

struct Job: Decodable {
  let base: String
  let path: String
  let subject: String
  let store: String
  let window: String
  let steps: [String]
  let out: String
  let viewportWidth: Int
  let viewportHeight: Int
  let windowWidth: Int
  let windowHeight: Int
  let readyTimeoutMs: Double
  let settleMs: Double
  let hiddenWaitMs: Double
}

/// Locked screen, a session that is not on the console, and a sleeping display all stop
/// WebKit from rendering a visible page, so each refuses a run.
func screenState() -> [String: Any] {
  var locked = false
  var onConsole = true
  if let d = CGSessionCopyCurrentDictionary() as? [String: Any] {
    if let v = d["CGSSessionScreenIsLocked"] as? Bool { locked = v }
    if let v = d["CGSSessionScreenIsLocked"] as? Int { locked = v != 0 }
    if let v = d[kCGSessionOnConsoleKey as String] as? Bool { onConsole = v }
  }
  let asleep = CGDisplayIsAsleep(CGMainDisplayID()) != 0
  return ["locked": locked, "onConsole": onConsole, "displayAsleep": asleep]
}

// Installed at document start in every page: visibility changes, uncaught errors, and a
// Resource Timing buffer large enough for a cold landing.
let instrument = """
(() => {
  if (window.__wk) { return; }
  const W = (window.__wk = { vis: [[Math.round(performance.now()), document.visibilityState]], errors: [] });
  try { performance.setResourceTimingBufferSize(4000); } catch (e) {}
  document.addEventListener("visibilitychange", () => { W.vis.push([Math.round(performance.now()), document.visibilityState]); });
  window.addEventListener("error", (e) => { W.errors.push(String((e && e.message) || e).slice(0, 200)); });
  window.addEventListener("unhandledrejection", (e) => { W.errors.push("unhandled rejection: " + String(e.reason && (e.reason.message || e.reason)).slice(0, 200)); });
})();
"""

@MainActor
final class Probe: NSObject, WKNavigationDelegate {
  let job: Job
  var webView: WKWebView!
  var window: NSWindow!
  var commitAt = 0.0
  var finishAt = 0.0
  var terminations = 0
  var navigationErrors: [String] = []
  var steps: [[String: Any]] = []

  init(job: Job) { self.job = job }

  func webView(_ webView: WKWebView, didCommit navigation: WKNavigation!) { commitAt = nowMs() }
  func webView(_ webView: WKWebView, didFinish navigation: WKNavigation!) { finishAt = nowMs() }
  func webView(_ webView: WKWebView, didFail navigation: WKNavigation!, withError error: Error) {
    navigationErrors.append("didFail: \(error.localizedDescription)")
  }
  func webView(
    _ webView: WKWebView, didFailProvisionalNavigation navigation: WKNavigation!, withError error: Error
  ) {
    navigationErrors.append("didFailProvisionalNavigation: \(error.localizedDescription)")
  }
  func webViewWebContentProcessDidTerminate(_ webView: WKWebView) { terminations += 1 }

  func js(_ source: String) async -> Any? {
    await withCheckedContinuation { (c: CheckedContinuation<Any?, Never>) in
      webView.evaluateJavaScript(source) { value, error in
        if let error = error {
          c.resume(returning: "JSERR: \(error.localizedDescription)")
        } else {
          c.resume(returning: value)
        }
      }
    }
  }
  func jsJSON(_ expr: String) async -> Any? {
    guard let s = await js("JSON.stringify(\(expr))") as? String, let d = s.data(using: .utf8) else {
      return nil
    }
    return try? JSONSerialization.jsonObject(with: d, options: [.fragmentsAllowed])
  }
  func truthy(_ expr: String) async -> Bool {
    let v = await js("!!(\(expr))")
    if let b = v as? Bool { return b }
    if let n = v as? NSNumber { return n.boolValue }
    return false
  }
  /// Polls from the native side, so a hidden page's throttled timers cannot slow the
  /// clock that times it. Returns the elapsed time when true, or nil on timeout.
  func waitFor(_ expr: String, from t0: Double, timeoutMs: Double) async -> Double? {
    while nowMs() - t0 < timeoutMs {
      if await truthy(expr) { return nowMs() - t0 }
      try? await Task.sleep(nanoseconds: 10_000_000)
    }
    return nil
  }
  /// Polls several expressions in one evaluation per tick and records when each first
  /// became true, until `stop` is true or the timeout passes. Times are from `t0`.
  func watch(_ exprs: [(String, String)], from t0: Double, until stop: String, timeoutMs: Double)
    async -> [String: Double]
  {
    var seen: [String: Double] = [:]
    // The outgoing document is marked before every load, so it can never satisfy a wait.
    let list = exprs.map { "!window.__wkOld && !!(\($0.1))" }.joined(separator: ", ")
    let start = nowMs()
    while nowMs() - start < timeoutMs {
      if let v = await js("[\(list)]") as? [Any] {
        for (i, e) in exprs.enumerated() where seen[e.0] == nil {
          let b = (v[i] as? Bool) ?? ((v[i] as? NSNumber)?.boolValue ?? false)
          if b { seen[e.0] = nowMs() - t0 }
        }
      }
      if seen[stop] != nil { break }
      try? await Task.sleep(nanoseconds: 10_000_000)
    }
    return seen
  }
  func sleepMs(_ ms: Double) async { try? await Task.sleep(nanoseconds: UInt64(ms * 1_000_000)) }
  func mark(_ step: String, _ at: String) async {
    guard let url = URL(string: "\(job.base)/__mark?step=\(step)&at=\(at)") else { return }
    _ = try? await URLSession.shared.data(from: url)
  }

  var subjectJS: String {
    let d = try? JSONSerialization.data(withJSONObject: [job.subject], options: [])
    let s = d.flatMap { String(data: $0, encoding: .utf8) } ?? "[\"\"]"
    return String(s.dropFirst().dropLast())
  }
  // The exact subject shown with content, the shared pending modifier cleared, and no
  // placeholder in the active view: the same subject test the transition scenario uses.
  var readyExpr: String {
    """
    (() => { const p = document.getElementById("preview-pane"); if (!p || p.dataset.renderedPath !== \(subjectJS)) { return false; }
      if (p.classList.contains("preview-navigation-pending")) { return false; }
      const a = p.querySelector(':scope > [data-active-view="true"]');
      return !!a && a.childElementCount > 0 && !a.querySelector(".loading, .mb-delayed-loading"); })()
    """
  }
  // Mounted does not depend on visibility: the subject rendered and the shell tools ready.
  var mountedExpr: String {
    """
    (() => { const p = document.getElementById("preview-pane");
      return !!p && p.dataset.renderedPath === \(subjectJS) && document.documentElement.dataset.shellToolsReady === "true"; })()
    """
  }
  let settledExpr =
    "document.documentElement.dataset.shellToolsReady === 'true' && window.METABROWSER_OPTIONAL_ASSETS_SETTLED === true"

  let factsExpr = """
    (() => {
      const n = performance.getEntriesByType("navigation")[0] || {};
      const fcp = performance.getEntriesByName("first-contentful-paint")[0];
      const res = performance.getEntriesByType("resource").map((e) => [e.name.replace(location.origin, ""), e.initiatorType, Math.round(e.transferSize || 0), Math.round(e.encodedBodySize || 0), Math.round(e.decodedBodySize || 0), e.responseStatus || 0]);
      const alerts = Array.from(document.querySelectorAll('#preview-pane [role="alert"], #preview-pane .preview-error, #tree-content [role="alert"]')).filter((x) => x.getBoundingClientRect().height > 0).map((x) => (x.textContent || "").trim().slice(0, 160));
      const W = window.__wk || { vis: [], errors: [] };
      return { href: location.href, navType: n.type || null, navTransferSize: Math.round(n.transferSize || 0),
        responseStart: Math.round(n.responseStart || 0), dcl: Math.round(n.domContentLoadedEventEnd || 0), load: Math.round(n.loadEventEnd || 0),
        fcp: fcp ? Math.round(fcp.startTime) : null, resources: res, vis: W.vis, errors: W.errors, alerts,
        w: innerWidth, h: innerHeight, version: ((document.querySelector(".menu-version") || {}).textContent || "").trim() || null,
        visibility: document.visibilityState, ua: navigator.userAgent };
    })()
    """

  func rafRate() async -> Any? {
    _ = await js(
      "window.__rafN = 0; window.__rafT = performance.now(); (function f() { window.__rafN++; if (performance.now() - window.__rafT < 500) { requestAnimationFrame(f); } })(); true"
    )
    await sleepMs(700)
    return await jsJSON("Math.round(window.__rafN * 1000 / 500)")
  }

  func makeWebView() -> Double {
    let t0 = nowMs()
    let config = WKWebViewConfiguration()
    if job.store == "ephemeral" {
      config.websiteDataStore = .nonPersistent()
    } else if let id = UUID(uuidString: job.store) {
      config.websiteDataStore = WKWebsiteDataStore(forIdentifier: id)
    }
    config.userContentController.addUserScript(
      WKUserScript(source: instrument, injectionTime: .atDocumentStart, forMainFrameOnly: true))
    let viewport = NSRect(x: 0, y: 0, width: job.viewportWidth, height: job.viewportHeight)
    webView = WKWebView(frame: viewport, configuration: config)
    webView.navigationDelegate = self
    // A small, nearly transparent, click-through window holds a web view of the full
    // viewport size; the page lays out at the viewport and only a corner is drawn.
    let screen = NSScreen.main?.visibleFrame ?? NSRect(x: 0, y: 0, width: 1440, height: 900)
    let frame = NSRect(
      x: screen.minX + 8, y: screen.minY + 8, width: CGFloat(job.windowWidth),
      height: CGFloat(job.windowHeight))
    let w = NSWindow(contentRect: frame, styleMask: [.borderless], backing: .buffered, defer: false)
    let holder = NSView(frame: NSRect(origin: .zero, size: frame.size))
    webView.frame = NSRect(
      x: 0, y: CGFloat(job.windowHeight - job.viewportHeight), width: CGFloat(job.viewportWidth),
      height: CGFloat(job.viewportHeight))
    holder.addSubview(webView)
    w.contentView = holder
    w.isReleasedWhenClosed = false
    w.alphaValue = 0.02
    w.ignoresMouseEvents = true
    w.level = .floating
    w.hasShadow = false
    window = w
    if job.window == "visible" { w.orderFrontRegardless() }
    return nowMs() - t0
  }

  func load() {
    if let url = URL(string: job.base + job.path) { webView.load(URLRequest(url: url)) }
  }

  func step(_ name: String) async {
    let screen0 = screenState()
    await mark(name, "start")
    var row: [String: Any] = ["step": name, "screenBefore": screen0]
    commitAt = 0
    finishAt = 0
    _ = await js("window.__wkOld = true")
    let t0 = nowMs()
    if name == "reload" { webView.reload() } else { load() }
    let exprs = [("mounted", mountedExpr), ("ready", readyExpr)]
    if name == "hidden-load-show" {
      let hidden = await watch(exprs, from: t0, until: "mounted", timeoutMs: job.readyTimeoutMs)
      row["hiddenMountedMs"] = hidden["mounted"].map { Int($0) } as Any
      // Whether the first view completes while hidden, given a fixed further wait.
      var readyHidden = hidden["ready"]
      if readyHidden == nil && hidden["mounted"] != nil {
        readyHidden = (await watch(exprs, from: t0, until: "ready", timeoutMs: job.hiddenWaitMs))["ready"]
      }
      row["hiddenReady"] = readyHidden != nil
      row["hiddenReadyMs"] = readyHidden.map { Int($0) } as Any
      row["visibilityHidden"] = await js("document.visibilityState") as Any
      row["rafHidden"] = await rafRate() as Any
      let t1 = nowMs()
      window.orderFrontRegardless()
      let shown = await watch(exprs, from: t1, until: "ready", timeoutMs: job.readyTimeoutMs)
      row["showToReadyMs"] = shown["ready"].map { Int($0) } as Any
      row["readyMs"] = shown["ready"].map { Int($0 + (t1 - t0)) } as Any
      row["visibilityShown"] = await js("document.visibilityState") as Any
    } else {
      let seen = await watch(exprs, from: t0, until: "ready", timeoutMs: job.readyTimeoutMs)
      row["readyMs"] = seen["ready"].map { Int($0) } as Any
      row["mountedMs"] = seen["mounted"].map { Int($0) } as Any
    }
    if commitAt > 0 { row["commitMs"] = Int(commitAt - t0) }
    _ = await waitFor(settledExpr, from: nowMs(), timeoutMs: 30000)
    await sleepMs(job.settleMs)
    if finishAt > 0 { row["finishMs"] = Int(finishAt - t0) }
    row["raf"] = await rafRate() as Any
    row["facts"] = await jsJSON(factsExpr) as Any
    await mark(name, "end")
    row["screenAfter"] = screenState()
    steps.append(row)
    FileHandle.standardError.write(
      "wkprobe \(name): ready \(row["readyMs"] ?? "none") ms\n".data(using: .utf8)!)
  }

  func run() async {
    var out: [String: Any] = ["job": job.store]
    if job.store.hasPrefix("remove:"), let id = UUID(uuidString: String(job.store.dropFirst(7))) {
      do {
        try await WKWebsiteDataStore.remove(forIdentifier: id)
        out["removed"] = true
      } catch {
        out["removed"] = false
        out["error"] = "\(error)"
      }
      write(out)
      return
    }
    let wk = Bundle(for: WKWebView.self).infoDictionary ?? [:]
    out["env"] = [
      "webkitVersion": wk["CFBundleVersion"] as? String ?? "",
      "webkitShortVersion": wk["CFBundleShortVersionString"] as? String ?? "",
      "os": ProcessInfo.processInfo.operatingSystemVersionString,
      "bundleIdentifier": Bundle.main.bundleIdentifier ?? "",
    ]
    out["screenAtStart"] = screenState()
    out["createWebViewMs"] = Int(makeWebView())
    out["launchToWebViewMs"] = Int(nowMs() - processStart)
    for s in job.steps { await step(s) }
    out["steps"] = steps
    out["terminations"] = terminations
    out["navigationErrors"] = navigationErrors
    write(out)
  }

  func write(_ out: [String: Any]) {
    if let d = try? JSONSerialization.data(withJSONObject: out, options: [.sortedKeys]) {
      try? d.write(to: URL(fileURLWithPath: job.out))
    }
  }
}

let app = NSApplication.shared
app.setActivationPolicy(.accessory)
guard CommandLine.arguments.count == 2, let data = CommandLine.arguments[1].data(using: .utf8),
  let job = try? JSONDecoder().decode(Job.self, from: data)
else {
  FileHandle.standardError.write("usage: mb-wkprobe JOB_JSON\n".data(using: .utf8)!)
  exit(2)
}
Task { @MainActor in
  let probe = Probe(job: job)
  await probe.run()
  exit(0)
}
app.run()
