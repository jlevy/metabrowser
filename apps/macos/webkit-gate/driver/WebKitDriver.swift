// The WebKit half of the measurement gate: a window holding the app's own web view.
//
// SwiftPM builds it as the WebKitDriver target (Package.swift) against the app's own
// modules: ShellViews for `WebContainerView` and `DropAwareWebView`, and ShellCore for
// `WebConfiguration` and `NavigationPolicy`. So the page runs in the app's web view
// class, built from the app's configuration, and navigations are decided by the app's
// policy. It is a measurement tool and never ships, which is why it may use two private
// WebKit interfaces: `_webProcessIdentifier`, to name the process whose memory run.mjs
// reads, and window occlusion detection, turned off as Chrome's flags turn off its own.
//
//   webkit-driver measure URL SCRIPT   inject SCRIPT at document start, load URL, print
//                                      the probe's record, then wait for a line on stdin
//   webkit-driver print URL PDF [N]    press the page's Print button, which calls
//                                      window.print(); the app's bridge hands it to
//                                      File > Print's path, here to PDF, at most N pages
//   webkit-driver drop URL PATH...     drop file URLs on the web view, as a drag from
//                                      Finder delivers them
//
// Each mode prints one JSON object on stdout and exits 0, or exits 1 with a message on
// stderr. The window is a fixed 1200 x 820 points, the content size the app's windows
// opened at before they were sized to the screen, kept so that runs compare.
import AppKit
import PDFKit
import ShellCore
import ShellViews
import WebKit

let contentSize = NSSize(width: 1200, height: 820)

struct Failure: Error, CustomStringConvertible {
    let description: String
}

func emit(_ object: [String: Any]) {
    let data: Data
    do {
        data = try JSONSerialization.data(withJSONObject: object, options: [.sortedKeys])
    } catch {
        fail("could not encode the result as JSON: \(error)")
    }
    FileHandle.standardOutput.write(data)
    FileHandle.standardOutput.write(Data("\n".utf8))
}

func fail(_ message: String) -> Never {
    FileHandle.standardError.write(Data("webkit-driver: \(message)\n".utf8))
    exit(1)
}

/// Resumes the print check when a modal print operation finishes. Nonisolated, because
/// AppKit may call it from the thread it printed on.
nonisolated final class PrintDone: NSObject, @unchecked Sendable {
    private var continuation: CheckedContinuation<Bool, Never>?
    /// AppKit holds the delegate only for the operation's lifetime, so this keeps it alive.
    private var retained: PrintDone?

    init(_ continuation: CheckedContinuation<Bool, Never>) {
        self.continuation = continuation
        super.init()
        retained = self
    }

    @objc func printOperationDidRun(
        _ operation: NSPrintOperation, success: Bool, contextInfo: UnsafeMutableRawPointer?
    ) {
        continuation?.resume(returning: success)
        continuation = nil
        retained = nil
    }
}

/// Records every page event the drop check listens for, posted by its user script.
final class PageEvents: NSObject, WKScriptMessageHandler {
    var events: [Any] = []

    func userContentController(_ controller: WKUserContentController, didReceive message: WKScriptMessage) {
        events.append(message.body)
    }
}

/// A dragging session as AppKit hands one to a drop target, for file URLs on a private
/// pasteboard. WebKit reads the pasteboard, location, and operation mask from it.
final class FileDrag: NSObject, NSDraggingInfo {
    let pasteboard: NSPasteboard
    let location: NSPoint
    let destination: NSWindow
    let sequence: Int

    init(urls: [URL], at location: NSPoint, in window: NSWindow, sequence: Int) {
        pasteboard = NSPasteboard(name: NSPasteboard.Name("metabrowser-webkit-gate-\(sequence)"))
        pasteboard.clearContents()
        pasteboard.writeObjects(urls as [NSURL])
        self.location = location
        destination = window
        self.sequence = sequence
    }

    var draggingDestinationWindow: NSWindow? { destination }
    var draggingSourceOperationMask: NSDragOperation { [.copy, .link, .generic] }
    var draggingLocation: NSPoint { location }
    var draggedImageLocation: NSPoint { location }
    var draggedImage: NSImage? { nil }
    var draggingPasteboard: NSPasteboard { pasteboard }
    var draggingSource: Any? { nil }
    var draggingSequenceNumber: Int { sequence }
    var draggingFormation: NSDraggingFormation {
        get { .default }
        set {}
    }
    var animatesToDestination: Bool {
        get { false }
        set {}
    }
    var numberOfValidItemsForDrop: Int {
        get { pasteboard.pasteboardItems?.count ?? 0 }
        set {}
    }
    var springLoadingHighlight: NSSpringLoadingHighlight { .none }
    func slideDraggedImage(to screenPoint: NSPoint) {}
    func enumerateDraggingItems(
        options enumOpts: NSDraggingItemEnumerationOptions = [], for view: NSView?,
        classes classArray: [AnyClass], searchOptions: [NSPasteboard.ReadingOptionKey: Any] = [:],
        using block: (NSDraggingItem, Int, UnsafeMutablePointer<ObjCBool>) -> Void
    ) {}
    func resetSpringLoading() {}
}

final class Driver: NSObject, NSApplicationDelegate, WKNavigationDelegate, WKUIDelegate {
    let mode: String
    let url: URL
    let arguments: [String]
    var window: NSWindow?
    var webView: DropAwareWebView?
    var policy = NavigationPolicy()
    let pageEvents = PageEvents()
    /// Navigations the policy decided, in order, for the checks to report.
    var decisions: [[String: String]] = []
    /// The paths of each drop the web view handed to the app (`onFileDrop`).
    var fileDrops: [[String]] = []
    var loaded = false
    var occlusionDetectionDisabled = false
    /// The app's bridge for the page's own Print button, installed as the app installs it.
    var pagePrints: PagePrintRequests?
    /// Every request the bridge delivered, with the policy's answer.
    var pagePrintRequests: [[String: Any]] = []
    /// The print path's result, once a print started; nil before.
    var printRecord: [String: Any]?
    var printing = false
    /// UI-delegate selectors naming printing that WebKit asked this delegate about. The
    /// app's delegate implements the same public methods as this one, so it answers the
    /// same way: no.
    nonisolated(unsafe) static var printSelectorsAsked: Set<String> = []

    nonisolated override func responds(to selector: Selector!) -> Bool {
        if let selector, NSStringFromSelector(selector).lowercased().contains("print") {
            Self.printSelectorsAsked.insert(NSStringFromSelector(selector))
        }
        return super.responds(to: selector)
    }

    init(mode: String, url: URL, arguments: [String]) {
        self.mode = mode
        self.url = url
        self.arguments = arguments
    }

    func applicationDidFinishLaunching(_ notification: Notification) {
        // As BrowserWindowController.pagePrints: the page's window.print() reaches
        // pageAskedToPrint, which answers it as the app does.
        let pagePrints = PagePrintRequests { [weak self] _, frame in self?.pageAskedToPrint(frame) }
        self.pagePrints = pagePrints
        let configuration = WebConfiguration.make(pagePrints: pagePrints)
        // A fresh store per run, like the scratch profile Chrome gets, so neither engine
        // starts with a warm HTTP cache. The rest of the configuration is the app's.
        configuration.websiteDataStore = .nonPersistent()
        let controller = configuration.userContentController
        switch mode {
        case "measure":
            guard let path = arguments.first else { fail("measure needs a script path") }
            let source: String
            do {
                source = try String(contentsOfFile: path, encoding: .utf8)
            } catch {
                fail("cannot read the script \(path): \(error.localizedDescription)")
            }
            controller.addUserScript(
                WKUserScript(source: source, injectionTime: .atDocumentStart, forMainFrameOnly: true))
        case "drop":
            controller.add(pageEvents, name: "gate")
            controller.addUserScript(
                WKUserScript(source: Self.dropListener, injectionTime: .atDocumentStart, forMainFrameOnly: true))
        default:
            break
        }

        let webView = DropAwareWebView(frame: .zero, configuration: configuration)
        // The counterpart of Chrome's --disable-backgrounding-occluded-windows, which run.mjs
        // passes: the page keeps its frames and priority when other windows or the lock
        // screen cover this one. WebKit SPI, used only by this tool.
        if webView.responds(to: Selector(("_setWindowOcclusionDetectionEnabled:"))) {
            webView.setValue(false, forKey: "windowOcclusionDetectionEnabled")
            occlusionDetectionDisabled = true
        }
        webView.navigationDelegate = self
        webView.uiDelegate = self
        webView.onFileDrop = { [weak self] urls in
            self?.fileDrops.append(urls.map(\.path))
            return true
        }
        let container = WebContainerView(webView: webView, statusView: NSView())
        container.showsStatus = false

        let window = NSWindow(
            contentRect: NSRect(origin: .zero, size: contentSize), styleMask: [.titled, .closable],
            backing: .buffered, defer: false)
        window.contentView = container
        // Above other windows, so the page is never occluded and WebKit never throttles it.
        window.level = .floating
        if let screen = NSScreen.main {
            let frame = screen.visibleFrame
            window.setFrameTopLeftPoint(NSPoint(x: frame.minX, y: frame.maxY))
        }
        window.title = "WebKit measurement gate"
        window.makeKeyAndOrderFront(nil)
        NSApp.activate()
        self.window = window
        self.webView = webView

        var origin = URLComponents()
        origin.scheme = url.scheme
        origin.host = url.host(percentEncoded: false)
        origin.port = url.port
        policy.origin = origin.url
        webView.load(URLRequest(url: url))
    }

    // MARK: The app's navigation decisions

    func webView(
        _ webView: WKWebView, decidePolicyFor action: WKNavigationAction,
        decisionHandler: @escaping @MainActor (WKNavigationActionPolicy) -> Void
    ) {
        let linkClick = action.navigationType == .linkActivated
        let decision = policy.decide(
            action.request.url, isMainFrame: action.targetFrame?.isMainFrame ?? true, isLinkClick: linkClick,
            shouldDownload: action.shouldPerformDownload,
            wantsNewWindow: linkClick && action.modifierFlags.contains(.command))
        decisions.append([
            "url": action.request.url?.absoluteString ?? "",
            "type": String(action.navigationType.rawValue),
            "decision": String(describing: decision),
        ])
        // The app opens a browser or another window here; this tool only records it.
        decisionHandler(decision == .allow ? .allow : .cancel)
    }

    func webView(_ webView: WKWebView, didFinish navigation: WKNavigation!) {
        guard !loaded else { return }
        loaded = true
        Task { @MainActor in
            do {
                switch mode {
                case "measure": try await measure()
                case "print": try await checkPrint()
                case "drop": try await checkDrop()
                default: fail("unknown mode \(mode)")
                }
            } catch {
                fail(String(describing: error))
            }
        }
    }

    func webView(_ webView: WKWebView, didFailProvisionalNavigation navigation: WKNavigation!, withError error: any Error) {
        fail("load failed: \(error.localizedDescription)")
    }

    func webViewWebContentProcessDidTerminate(_ webView: WKWebView) {
        fail("the web content process terminated")
    }

    // MARK: Modes

    func measure() async throws {
        guard let webView else { return }
        let value = try await webView.callAsyncJavaScript(
            "return JSON.stringify(await globalThis.__webkitGate.done);", arguments: [:], in: nil, contentWorld: .page)
        guard let text = value as? String, let data = text.data(using: .utf8),
              let record = try JSONSerialization.jsonObject(with: data) as? [String: Any]
        else { throw Failure(description: "the probe returned no record") }
        var output = record
        output["engine"] = engineFacts()
        output["web_process_pid"] = webView.value(forKey: "_webProcessIdentifier") as? Int ?? NSNull()
        emit(output)
        // run.mjs reads the web process's footprint now, then closes stdin.
        _ = FileHandle.standardInput.readDataToEndOfFile()
        exit(0)
    }

    /// The page's Print button, which calls `window.print()`, and the print path it reaches.
    ///
    /// The app answers an allowed request with File > Print's path (`pageAskedToPrint`), so
    /// the print starts from the request here too. If no request starts it, the check runs
    /// that path itself, as File > Print does, and the record says which started it.
    func checkPrint() async throws {
        guard let webView else { return }
        let windowsBefore = NSApp.windows.count
        let called = try await webView.callAsyncJavaScript(
            """
            const visible = () => {
              const button = document.querySelector(".file-header-print");
              return button && !button.hidden && !button.disabled && !button.closest("[hidden]") ? button : null;
            };
            for (let waited = 0; !visible() && waited < 15000; waited += 100) {
              await new Promise((resolve) => setTimeout(resolve, 100));
            }
            const button = visible();
            if (button) { button.click(); return "the Print button (.file-header-print)"; }
            window.print();
            return "window.print() directly: no Print button appeared";
            """, arguments: [:], in: nil, contentWorld: .page)
        // The same 3 s the check waited for a panel before the bridge existed.
        var waited = 0
        while !printing, waited < 30 {
            try await Task.sleep(for: .milliseconds(100))
            waited += 1
        }
        let pagePrint: [String: Any] = [
            "called": called as? String ?? "",
            "requests": pagePrintRequests,
            "reached_print_path": printing,
            "windows_before": windowsBefore,
            "windows_after": NSApp.windows.count,
            "print_selectors_webkit_asked_for": Self.printSelectorsAsked.sorted(),
        ]
        if !printing {
            startPrint(startedBy: "File > Print: no page request started a print")
        }
        while printRecord == nil {
            try await Task.sleep(for: .milliseconds(100))
        }
        emit([
            "engine": engineFacts(),
            "page_print": pagePrint,
            "print_operation": printRecord ?? [:],
            "navigations": decisions,
        ])
        exit(0)
    }

    /// The app's answer to the page's Print button (`BrowserWindowController`'s
    /// `pageAskedToPrint`): the same policy, then File > Print's path. Only the print check
    /// prints; another mode records the request alone.
    func pageAskedToPrint(_ frame: WKFrameInfo) {
        let sheetOpen = window?.attachedSheet != nil
        let allowed = PagePrintRequests.allows(frame, under: policy, sheetOpen: sheetOpen)
        let origin = frame.securityOrigin
        pagePrintRequests.append([
            "frame_url": frame.request.url?.absoluteString ?? "",
            "frame_origin": "\(origin.protocol)://\(origin.host):\(origin.port)",
            "main_frame": frame.isMainFrame,
            "sheet_open": sheetOpen,
            "allowed": allowed,
        ])
        guard allowed, mode == "print", !printing else { return }
        startPrint(startedBy: "the page's Print request")
    }

    /// File > Print in the app (`printPage`): printOperation(with:) run modally for the
    /// window, here saved to a PDF of at most the page limit instead of shown in a panel.
    func startPrint(startedBy: String) {
        guard let webView, let window else { return }
        printing = true
        let pdfPath = arguments.first ?? "webkit-gate-print.pdf"
        // At most this many pages, a safety net for a document that never stops paginating.
        let lastPage = arguments.count > 1 ? Int(arguments[1]) ?? 50 : 50
        let info = NSPrintInfo.shared.copy() as! NSPrintInfo
        info.jobDisposition = .save
        info.dictionary()[NSPrintInfo.AttributeKey.allPages] = false
        info.dictionary()[NSPrintInfo.AttributeKey.firstPage] = 1
        info.dictionary()[NSPrintInfo.AttributeKey.lastPage] = lastPage
        info.dictionary()[NSPrintInfo.AttributeKey.jobSavingURL] = URL(fileURLWithPath: pdfPath)
        let operation = webView.printOperation(with: info)
        operation.showsPrintPanel = false
        operation.showsProgressPanel = false
        operation.view?.frame = webView.bounds
        Task { @MainActor in
            // runModal(for:), as the app calls it: WebKit computes the pages asynchronously,
            // and a synchronous run() here printed blank pages until it was stopped at 865 MB.
            let started = Date()
            let printed = await withCheckedContinuation { continuation in
                let done = PrintDone(continuation)
                operation.runModal(
                    for: window, delegate: done,
                    didRun: #selector(PrintDone.printOperationDidRun(_:success:contextInfo:)), contextInfo: nil)
            }
            let seconds = Date().timeIntervalSince(started)
            let pdf = URL(fileURLWithPath: pdfPath)
            // No file means nothing was printed, which the record reports as 0 bytes.
            let size = (try? pdf.resourceValues(forKeys: [.fileSizeKey]).fileSize) ?? 0
            let document = PDFDocument(url: pdf)
            printRecord = [
                "started_by": startedBy, "ran": printed, "pdf_bytes": size,
                "pdf_pages": document?.pageCount ?? 0, "page_limit": lastPage,
                "first_page_text": String((document?.page(at: 0)?.string ?? "").prefix(160)),
                "seconds": (seconds * 10).rounded() / 10,
            ]
        }
    }

    /// Drags each path onto the middle of the page and drops it, one at a time.
    func checkDrop() async throws {
        guard let webView, let window else { return }
        var drops: [[String: Any]] = []
        let point = webView.convert(NSPoint(x: webView.bounds.midX, y: webView.bounds.midY), to: nil)
        for (index, path) in arguments.enumerated() {
            let urlBefore = webView.url?.absoluteString ?? ""
            let decisionsBefore = decisions.count
            let fileDropsBefore = fileDrops.count
            let eventsBefore = pageEvents.events.count
            let drag = FileDrag(urls: [URL(fileURLWithPath: path)], at: point, in: window, sequence: 1000 + index)
            let entered = webView.draggingEntered(drag)
            // WebKit answers a drag update from the web process asynchronously, so ask
            // again after the page has had time to see dragenter and dragover.
            var updated = webView.draggingUpdated(drag)
            for _ in 0..<10 {
                try await Task.sleep(for: .milliseconds(100))
                updated = webView.draggingUpdated(drag)
            }
            let prepared = webView.prepareForDragOperation(drag)
            let performed = webView.performDragOperation(drag)
            webView.concludeDragOperation(drag)
            try await Task.sleep(for: .seconds(2))
            drops.append([
                "path": path,
                "dragging_entered": entered.rawValue,
                "dragging_updated": updated.rawValue,
                "prepare": prepared,
                "perform": performed,
                "page_events": Array(pageEvents.events[eventsBefore...]),
                "navigations": Array(decisions[decisionsBefore...]),
                "app_opens": Array(fileDrops[fileDropsBefore...]),
                "url_before": urlBefore,
                "url_after": webView.url?.absoluteString ?? "",
            ])
        }
        emit(["engine": engineFacts(), "drops": drops])
        exit(0)
    }

    /// Listens without handling: a page that does not call preventDefault() gets
    /// WebKit's default drop.
    static let dropListener = """
        for (const type of ["dragenter", "dragover", "drop"]) {
          addEventListener(type, (event) => {
            if (type === "dragover" && window.__gateSawOver) { return; }
            if (type === "dragover") { window.__gateSawOver = true; }
            const files = event.dataTransfer ? Array.from(event.dataTransfer.files).map((f) => f.name) : [];
            const types = event.dataTransfer ? Array.from(event.dataTransfer.types) : [];
            const message = { type, files, types, defaultPrevented: event.defaultPrevented };
            window.webkit.messageHandlers.gate.postMessage(message);
          }, true);
        }
        """

    func engineFacts() -> [String: Any] {
        let webKit = Bundle(for: WKWebView.self)
        let os = ProcessInfo.processInfo.operatingSystemVersion
        return [
            "name": "WKWebView",
            "webkit_bundle_version": webKit.infoDictionary?["CFBundleVersion"] as? String ?? "",
            "macos": "\(os.majorVersion).\(os.minorVersion).\(os.patchVersion)",
            "occlusion_detection_disabled": occlusionDetectionDisabled,
        ]
    }
}

@main
enum Entry {
    static func main() {
        let commandLine = CommandLine.arguments
        guard commandLine.count >= 3, let target = URL(string: commandLine[2]) else {
            fail("usage: webkit-driver measure|print|drop URL [ARGS...]")
        }
        let app = NSApplication.shared
        app.setActivationPolicy(.regular)
        // No App Nap while a sample runs, whatever covers the window: the app a reader
        // uses is frontmost, and Chrome's flags keep its renderer at full speed too.
        let activity = ProcessInfo.processInfo.beginActivity(
            options: [.userInitiated, .latencyCritical], reason: "WebKit measurement gate")
        let driver = Driver(mode: commandLine[1], url: target, arguments: Array(commandLine.dropFirst(3)))
        app.delegate = driver
        DispatchQueue.main.asyncAfter(deadline: .now() + .seconds(600)) { fail("no result after 600 s") }
        app.run()
        ProcessInfo.processInfo.endActivity(activity)
    }
}
