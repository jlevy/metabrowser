import AppKit
import CoreServices
import Foundation
import Testing
import WebKit
@testable import ShellCore

/// Records each link the page follows, and whether it would have downloaded, and cancels
/// it; and says whether the fixture loaded.
private final class LinkWatcher: NSObject, WKNavigationDelegate {
    var loaded = false
    var networkProcessEnded = false
    /// Each link followed: its URL and whether WebKit would download it, which in a folder
    /// window opens the save panel (`NavigationPolicy.decide`).
    var followed: [(url: URL, download: Bool)] = []

    func webView(_ webView: WKWebView, didFinish navigation: WKNavigation!) { loaded = true }

    func webView(_ webView: WKWebView, didFailProvisionalNavigation navigation: WKNavigation!, withError error: any Error) {
        if isNetworkProcessLoss(error) { networkProcessEnded = true }
    }

    func webView(
        _ webView: WKWebView, decidePolicyFor action: WKNavigationAction,
        decisionHandler: @escaping @MainActor (WKNavigationActionPolicy) -> Void
    ) {
        guard action.navigationType == .linkActivated, let url = action.request.url else {
            return decisionHandler(.allow)
        }
        followed.append((url, action.shouldPerformDownload))
        decisionHandler(.cancel)
    }
}

/// The Open link's script, its handler, and the host descriptor in a real `WKWebView`, and
/// a downloaded copy through a real `WKDownload`. Runs in a process of its own, with the
/// other WebKit suites; see `ignoreSIGPIPELikeTheApp`.
@Suite struct OpenFileWebKitTests {
    init() { ignoreSIGPIPELikeTheApp() }

    private let origin = URL(string: "http://127.0.0.1:8411/view/")!
    private let policy = NavigationPolicy(origin: URL(string: "http://127.0.0.1:8411")!)
    /// The header `/raw` sends with active content on: `capabilities.raw_sandbox_csp`.
    private let rawSandbox = "Content-Security-Policy: sandbox allow-scripts allow-popups allow-forms allow-downloads"

    /// The `pdf` plugin's Open link as its contract has it, and its Download link, which has
    /// no marker: each a 200 by 100 block in a 600 by 400 web view, Open from (300, 20) and
    /// Download from (300, 250), in CSS pixels from the top left. Below them an iframe of
    /// the page's own origin.
    private let page = """
        <body style="margin:0">
        <a id="open" href="/raw?path=docs%2Fa%20b.pdf" data-metabrowser-open-file="filesystem" download="a b.pdf"
          style="position:absolute;left:300px;top:20px;display:block;width:200px;height:100px"><span id="mark">Open</span></a>
        <a id="download" href="/raw?path=docs%2Fa%20b.pdf" download="a b.pdf"
          style="position:absolute;left:300px;top:250px;display:block;width:200px;height:100px">Download</a>
        <iframe srcdoc="<p>inner</p>" style="position:absolute;left:0;top:0;width:100px;height:100px"></iframe>
        </body>
        """
    /// Window points, up from the bottom of the 400-point window: the middle of each link.
    private let onOpen = NSPoint(x: 400, y: 400 - 70)
    private let onDownload = NSPoint(x: 400, y: 400 - 300)

    private func configuration(_ requests: OpenFileRequests?) -> WKWebViewConfiguration {
        let configuration = WebConfiguration.make(openFiles: requests)
        configuration.websiteDataStore = .nonPersistent()  // tests leave no cookies behind
        return configuration
    }

    /// `page` in a 600 by 400 web view, in a window when `shown`, for trusted clicks.
    private func load(
        _ html: String, requests: OpenFileRequests?, shown: Bool = false
    ) async -> (WKWebView, LinkWatcher, NSWindow?) {
        let webView = WKWebView(frame: NSRect(x: 0, y: 0, width: 600, height: 400), configuration: configuration(requests))
        let watcher = LinkWatcher()
        webView.navigationDelegate = watcher
        webView.loadHTMLString(html, baseURL: origin)
        #expect(await eventually { watcher.loaded })
        guard shown else { return (webView, watcher, nil) }
        let window = NSWindow(
            contentRect: NSRect(x: 0, y: 0, width: 600, height: 400), styleMask: [.titled], backing: .buffered,
            defer: false)
        window.contentView = webView
        window.orderFrontRegardless()
        return (webView, watcher, window)
    }

    /// `body` from a local server, under `headers`, as a `/raw` response is served.
    private func serve(
        _ body: String, headers: [String], requests: OpenFileRequests?
    ) async throws -> (WKWebView, LinkWatcher, LocalHTTPServer, NSWindow) {
        let server = try LocalHTTPServer(body: Data(body.utf8), contentType: "text/html; charset=utf-8", headers: headers)
        let url = server.start()
        let webView = WKWebView(frame: NSRect(x: 0, y: 0, width: 600, height: 400), configuration: configuration(requests))
        let watcher = LinkWatcher()
        webView.navigationDelegate = watcher
        webView.load(URLRequest(url: url))
        do {
            #expect(try await eventually(unlessLost: { watcher.networkProcessEnded }) { watcher.loaded })
        } catch {
            server.stop()
            throw error
        }
        let window = NSWindow(
            contentRect: NSRect(x: 0, y: 0, width: 600, height: 400), styleMask: [.titled], backing: .buffered,
            defer: false)
        window.contentView = webView
        window.orderFrontRegardless()
        return (webView, watcher, server, window)
    }

    // MARK: - The Open link

    /// The handler lives in the app's own content world: the page's scripts cannot see it.
    @Test func thePageCannotReachTheHandler() async throws {
        let (webView, _, _) = await load(page, requests: OpenFileRequests { _, _, _ in })
        let fromPage = try await webView.evaluateJavaScript(
            "typeof window.webkit?.messageHandlers?.\(OpenFileRequests.handlerName)")
        #expect(fromPage as? String == "undefined")
        let fromApp = try await webView.evaluateJavaScript(
            "typeof window.webkit.messageHandlers.\(OpenFileRequests.handlerName)", in: nil,
            contentWorld: OpenFileRequests.world)
        #expect(fromApp as? String == "object")
    }

    /// The user's click on the Open link reaches the app with the link's file, and the link
    /// downloads nothing. A Command-click on it, and a click on the Download link, which has
    /// no marker, are left to the link: a download, which a folder window saves through its
    /// save panel.
    @Test func theUsersClickOnTheOpenLinkReachesTheAppAlone() async throws {
        let requests = Recorder<OpenFileRequests.Request>()
        let accepted = Recorder<Bool>()
        let policy = policy
        let openFiles = OpenFileRequests { _, frame, request in
            requests.append(request)
            accepted.append(OpenFileRequests.allows(frame, request, under: policy))
        }
        let (webView, watcher, shown) = await load(page, requests: openFiles, shown: true)
        let window = try #require(shown)
        defer { window.orderOut(nil) }

        click(webView, at: onOpen, in: window)
        #expect(await eventually(within: .seconds(10)) { requests.count == 1 })
        let request = try #require(requests.all.first)
        #expect(request.href.absoluteString == "http://127.0.0.1:8411/raw?path=docs%2Fa%20b.pdf")
        #expect(request.subject == .filesystem)
        #expect(request.path == "docs/a b.pdf")
        #expect(request.name == "a b.pdf")
        #expect(accepted.all == [true])

        click(webView, at: onOpen, in: window, modifiers: .command)
        #expect(await eventually(within: .seconds(10)) { watcher.followed.count == 1 })
        click(webView, at: onDownload, in: window)
        #expect(await eventually(within: .seconds(10)) { watcher.followed.count == 2 })
        #expect(watcher.followed.map { $0.download } == [true, true])
        #expect(watcher.followed.map { $0.url.path } == ["/raw", "/raw"])
        #expect(requests.count == 1)
    }

    /// A click a script dispatches is not the user's: it reaches no handler, and the link
    /// downloads, as it would without the app.
    @Test func aScriptedClickIsLeftToTheLink() async throws {
        let requests = Recorder<OpenFileRequests.Request>()
        let (webView, watcher, _) = await load(page, requests: OpenFileRequests { _, _, request in
            requests.append(request)
        })
        _ = try await webView.evaluateJavaScript("document.getElementById('mark').click()")
        #expect(await eventually(within: .seconds(10)) { watcher.followed.count == 1 })
        #expect(watcher.followed.first?.download == true)
        try await Task.sleep(for: .milliseconds(200))
        #expect(requests.count == 0)
        withExtendedLifetime(webView) {}
    }

    /// A sandboxed `/raw` document, whose origin is opaque, cannot use a marked link of its
    /// own: the script leaves the user's click on it to the link, and a message posted to
    /// the handler from the app's own world, as no page can, is refused by the window's check.
    /// The link then navigates rather than downloads: WebKit honors `download` only for a
    /// URL of the document's own origin, and an opaque origin is no URL's.
    @Test func aSandboxedRawDocumentsMarkedLinkOpensNothing() async throws {
        let received = Recorder<OpenFileRequests.Request>()
        let accepted = Recorder<Bool>()
        let openFiles = OpenFileRequests { _, frame, request in
            received.append(request)
            // The server's own origin is the link's.
            accepted.append(OpenFileRequests.allows(frame, request, under: NavigationPolicy(origin: request.href)))
        }
        let (webView, watcher, server, window) = try await serve(page, headers: [rawSandbox], requests: openFiles)
        defer {
            window.orderOut(nil)
            server.stop()
        }
        #expect(try await webView.evaluateJavaScript("self.origin") as? String == "null")

        click(webView, at: onOpen, in: window)
        #expect(await eventually(within: .seconds(10)) { watcher.followed.count == 1 })
        #expect(watcher.followed.first?.url.path == "/raw")
        #expect(watcher.followed.first?.download == false)
        #expect(received.count == 0)

        _ = try await webView.evaluateJavaScript(
            """
            window.webkit.messageHandlers.\(OpenFileRequests.handlerName).postMessage({
                href: new URL("/raw?path=a.pdf", location.href).href, subject: "filesystem", name: "a.pdf"}); 0
            """, in: nil, contentWorld: OpenFileRequests.world)
        #expect(await eventually(within: .seconds(10)) { received.count == 1 })
        #expect(accepted.all == [false])
    }

    // MARK: - The host descriptor

    /// What the page sees of `window.metabrowserHost`, after trying to change it.
    private func descriptor(in webView: WKWebView) async throws -> [String: Any] {
        let result = try await webView.callAsyncJavaScript(
            """
            const host = window.\(HostDescriptor.name);
            const property = Object.getOwnPropertyDescriptor(window, "\(HostDescriptor.name)");
            try { window.\(HostDescriptor.name) = { actions: ["other"] }; } catch {}
            try { host.actions.push("other"); } catch {}
            let deleted = false;
            try { deleted = delete window.\(HostDescriptor.name); } catch {}
            const frame = document.querySelector("iframe");
            let inFrame = "no frame";
            try { inFrame = frame ? typeof frame.contentWindow.\(HostDescriptor.name) : inFrame; } catch { inFrame = "blocked"; }
            return {
                type: typeof host,
                actions: host ? [...host.actions] : null,
                frozen: host ? Object.isFrozen(host) && Object.isFrozen(host.actions) : null,
                writable: property ? property.writable : null,
                configurable: property ? property.configurable : null,
                same: window.\(HostDescriptor.name) === host,
                deleted,
                inFrame,
                origin: self.origin,
            };
            """, arguments: [:], in: nil, contentWorld: .page)
        return try #require(result as? [String: Any])
    }

    /// The page's main frame of the server's origin reads a frozen descriptor that names
    /// `open-file` and that its scripts cannot change; a frame inside it reads none.
    @Test func theDescriptorIsInThePageAndCannotBeChanged() async throws {
        let (webView, _, _) = await load(page, requests: OpenFileRequests { _, _, _ in })
        let seen = try await descriptor(in: webView)
        #expect(seen["type"] as? String == "object")
        #expect(seen["actions"] as? [String] == [OpenFileRequests.action])
        #expect(seen["frozen"] as? Bool == true)
        #expect(seen["writable"] as? Bool == false)
        #expect(seen["configurable"] as? Bool == false)
        #expect(seen["same"] as? Bool == true)
        #expect(seen["deleted"] as? Bool == false)
        #expect(seen["inFrame"] as? String == "undefined")
        #expect(seen["origin"] as? String == "http://127.0.0.1:8411")
    }

    /// A configuration with no Open handler publishes no descriptor: it would name an
    /// action nothing answers.
    @Test func noHandlerNoDescriptor() async throws {
        let (webView, _, _) = await load(page, requests: nil)
        #expect(try await descriptor(in: webView)["type"] as? String == "undefined")
    }

    /// A sandboxed `/raw` document, whose origin is opaque, gets no descriptor.
    @Test func aSandboxedRawDocumentHasNoDescriptor() async throws {
        let (webView, _, server, window) = try await serve(
            page, headers: [rawSandbox], requests: OpenFileRequests { _, _, _ in })
        defer {
            window.orderOut(nil)
            server.stop()
        }
        let seen = try await descriptor(in: webView)
        #expect(seen["origin"] as? String == "null")
        #expect(seen["type"] as? String == "undefined")
    }

    // MARK: - A downloaded copy

    private let pdf = Data(("%PDF-1.4\n%\u{E2}\u{E3}\n" + String(repeating: "0 0 obj\n", count: 200)).utf8)

    /// Downloads `server`'s answer as `name` into `directory` and waits for the result.
    private func copy(
        from server: LocalHTTPServer, named name: String, into directory: URL
    ) async throws -> Result<URL, OpenFileFailure> {
        let url = server.start()
        let downloads = OpenFileDownloads(directory: directory)
        let webView = WKWebView(frame: .zero, configuration: WKWebViewConfiguration())
        let results = Recorder<Result<URL, OpenFileFailure>>()
        downloads.start(url, named: name, in: webView) { results.append($0) }
        #expect(await eventually { results.count == 1 })
        withExtendedLifetime((webView, downloads)) {}
        return try #require(results.all.first)
    }

    /// A finished copy is the served bytes, in a folder of its own, quarantined as a web
    /// download by Metabrowser and read-only.
    @Test func aDownloadedCopyIsQuarantinedAndReadOnly() async throws {
        let directory = try temporaryDirectory()
        defer { try? FileManager.default.removeItem(at: directory) }
        let server = try LocalHTTPServer(body: pdf, contentType: "application/pdf")
        defer { server.stop() }
        let copy = try await copy(from: server, named: "a b.pdf", into: directory).get()
        #expect(copy.lastPathComponent == "a b.pdf")
        #expect(copy.deletingLastPathComponent().deletingLastPathComponent().path == directory.path)
        #expect(FileManager.default.contents(atPath: copy.path) == pdf)
        let quarantine = try #require(try copy.resourceValues(forKeys: [.quarantinePropertiesKey]).quarantineProperties)
        #expect(quarantine[kLSQuarantineAgentNameKey as String] as? String == "Metabrowser")
        #expect(quarantine[kLSQuarantineTypeKey as String] as? String == kLSQuarantineTypeWebDownload as String)
        #expect(!FileManager.default.isWritableFile(atPath: copy.path))
    }

    /// A server that answers with an error leaves nothing behind, and says what it answered.
    @Test func anErrorAnswerLeavesNothing() async throws {
        let directory = try temporaryDirectory()
        defer { try? FileManager.default.removeItem(at: directory) }
        let server = try LocalHTTPServer(body: Data("not found".utf8), contentType: "text/plain", status: "404 Not Found")
        defer { server.stop() }
        let result = try await copy(from: server, named: "a b.pdf", into: directory)
        guard case .failure(let failure) = result else {
            Issue.record("downloaded \(result)")
            return
        }
        #expect(failure.name == "a b.pdf")
        #expect(failure.reason.hasSuffix("(404)"), "\(failure.reason)")
        #expect(try FileManager.default.contentsOfDirectory(atPath: directory.path).isEmpty)
    }

    /// A copy whose type the app does not open is removed, not opened.
    @Test func aCopyOfATypeTheAppDoesNotOpenIsRemoved() async throws {
        let directory = try temporaryDirectory()
        defer { try? FileManager.default.removeItem(at: directory) }
        let server = try LocalHTTPServer(body: Data("#!/bin/sh\n".utf8))
        defer { server.stop() }
        let result = try await copy(from: server, named: "run.command", into: directory)
        #expect(result == .failure(OpenFileFailure(name: "run.command", reason: OpenFileTypes.refusal)))
        #expect(try FileManager.default.contentsOfDirectory(atPath: directory.path).isEmpty)
    }

    private func click(
        _ webView: WKWebView, at point: NSPoint, in window: NSWindow, modifiers: NSEvent.ModifierFlags = []
    ) {
        for type in [NSEvent.EventType.leftMouseDown, .leftMouseUp] {
            guard let event = NSEvent.mouseEvent(
                with: type, location: point, modifierFlags: modifiers, timestamp: ProcessInfo.processInfo.systemUptime,
                windowNumber: window.windowNumber, context: nil, eventNumber: 0, clickCount: 1, pressure: 1)
            else { continue }
            if type == .leftMouseDown { webView.mouseDown(with: event) } else { webView.mouseUp(with: event) }
        }
    }
}
