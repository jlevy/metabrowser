import Foundation
import Network
@testable import ShellCore

/// A one-response HTTP server on 127.0.0.1, for driving a real `WKDownload`.
///
/// Every request gets `body` under a `Content-Length` of `declaredLength`. When the body
/// is shorter than that, the connection then waits for `release()` and is reset, which
/// `WKDownload` reports as a failure after it has written part of the file.
nonisolated final class LocalHTTPServer: @unchecked Sendable {
    let body: Data
    let declaredLength: Int
    private let listener: NWListener
    private let released = Latch<Void>()
    private let sent = Latch<Void>()

    init(body: Data, declaredLength: Int? = nil) throws {
        self.body = body
        self.declaredLength = declaredLength ?? body.count
        let parameters = NWParameters.tcp
        parameters.requiredLocalEndpoint = NWEndpoint.hostPort(host: "127.0.0.1", port: .any)
        listener = try NWListener(using: parameters)
        listener.newConnectionHandler = { [weak self] connection in self?.serve(connection) }
    }

    /// Starts listening and returns the URL of the file it serves.
    func start() async -> URL {
        let ready = Latch<UInt16>()
        listener.stateUpdateHandler = { [listener] state in
            if case .ready = state, let port = listener.port { ready.resolve(port.rawValue) }
        }
        listener.start(queue: .global())
        let port = await ready.wait() ?? 0
        return URL(string: "http://127.0.0.1:\(port)/file.bin")!
    }

    /// Returns once the response's bytes have been handed to the connection.
    func waitUntilSent() async { _ = await sent.wait() }

    /// Lets a short response reset its connection.
    func release() { released.resolve(()) }

    func stop() { listener.cancel() }

    private func serve(_ connection: NWConnection) {
        connection.start(queue: .global())
        connection.receive(minimumIncompleteLength: 1, maximumLength: 65_536) { [self] _, _, _, _ in
            var response = Data(
                ("HTTP/1.1 200 OK\r\nContent-Type: application/octet-stream\r\n"
                    + "Content-Length: \(declaredLength)\r\nConnection: close\r\n\r\n").utf8)
            response.append(body)
            connection.send(content: response, completion: .contentProcessed { [self] _ in
                sent.resolve(())
                guard body.count < declaredLength else {
                    return connection.send(
                        content: nil, isComplete: true, completion: .contentProcessed { _ in connection.cancel() })
                }
                Task {
                    _ = await released.wait()
                    connection.forceCancel()
                }
            })
        }
    }
}
