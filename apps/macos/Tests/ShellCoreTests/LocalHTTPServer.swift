import Darwin
import Foundation
import os
@testable import ShellCore

/// A one-response HTTP server on 127.0.0.1, for driving a real `WKDownload`, on plain
/// sockets so every byte and every close is the test's.
///
/// Every request gets `body` under a `Content-Length` of `declaredLength`. A full
/// response ends with an orderly close after the client's own. When the body is shorter
/// than declared, the connection waits for `release()` and is then reset, which
/// `WKDownload` reports as a failure after it has written part of the file.
nonisolated final class LocalHTTPServer: @unchecked Sendable {
    let body: Data
    let declaredLength: Int
    let url: URL
    private let listener: Int32
    private let sent = Latch<Void>()
    private let released = DispatchSemaphore(value: 0)
    private let stopped = OSAllocatedUnfairLock(initialState: false)

    init(body: Data, declaredLength: Int? = nil) throws {
        self.body = body
        self.declaredLength = declaredLength ?? body.count
        let listener = Darwin.socket(AF_INET, SOCK_STREAM, 0)
        guard listener >= 0 else { throw POSIXError(.EIO) }
        var address = sockaddr_in()
        address.sin_len = UInt8(MemoryLayout<sockaddr_in>.size)
        address.sin_family = sa_family_t(AF_INET)
        address.sin_addr.s_addr = inet_addr("127.0.0.1")
        address.sin_port = 0
        var length = socklen_t(MemoryLayout<sockaddr_in>.size)
        let bound = withUnsafeMutablePointer(to: &address) { pointer in
            pointer.withMemoryRebound(to: sockaddr.self, capacity: 1) { address in
                bind(listener, address, length) == 0 && listen(listener, 8) == 0
                    && getsockname(listener, address, &length) == 0
            }
        }
        guard bound else {
            close(listener)
            throw POSIXError(.EADDRNOTAVAIL)
        }
        self.listener = listener
        url = URL(string: "http://127.0.0.1:\(UInt16(bigEndian: address.sin_port))/file.bin")!
    }

    /// Starts answering requests and returns the URL of the file it serves.
    func start() -> URL {
        Thread.detachNewThread { [self] in acceptLoop() }
        return url
    }

    /// Whether the response's bytes reached the socket within `limit`.
    func waitUntilSent(within limit: Duration = .seconds(10)) async -> Bool {
        let sent = self.sent
        return await firstResult(within: limit, of: [{ @Sendable in await sent.wait() }]) != nil
    }

    /// Lets a short response reset its connection.
    func release() { released.signal() }

    func stop() {
        stopped.withLock { $0 = true }
        release()
    }

    private var isStopped: Bool { stopped.withLock { $0 } }

    private func acceptLoop() {
        defer { close(listener) }
        while !isStopped {
            var ready = pollfd(fd: listener, events: Int16(POLLIN), revents: 0)
            guard poll(&ready, 1, 50) > 0 else { continue }
            let connection = accept(listener, nil, nil)
            guard connection >= 0 else { continue }
            var on: Int32 = 1
            setsockopt(connection, SOL_SOCKET, SO_NOSIGPIPE, &on, socklen_t(MemoryLayout<Int32>.size))
            Thread.detachNewThread { [self] in serve(connection) }
        }
    }

    private func serve(_ connection: Int32) {
        // The whole request first: closing with request bytes unread makes the kernel
        // reset the connection, and the client loses the response it was reading.
        var request = Data()
        var buffer = [UInt8](repeating: 0, count: 4096)
        while request.range(of: Data("\r\n\r\n".utf8)) == nil {
            let count = read(connection, &buffer, buffer.count)
            guard count > 0 else { return _ = close(connection) }
            request.append(contentsOf: buffer[..<count])
        }
        var response = Data(
            ("HTTP/1.1 200 OK\r\nContent-Type: application/octet-stream\r\n"
                + "Content-Length: \(declaredLength)\r\nX-Content-Type-Options: nosniff\r\nConnection: close\r\n\r\n").utf8)
        response.append(body)
        let written = response.withUnsafeBytes { write(connection, $0.baseAddress, $0.count) }
        sent.resolve(())
        guard written == response.count, body.count < declaredLength else {
            // An orderly close: end the response, then wait for the client to close.
            shutdown(connection, SHUT_WR)
            while read(connection, &buffer, buffer.count) > 0 {}
            close(connection)
            return
        }
        released.wait()
        var reset = linger(l_onoff: 1, l_linger: 0)  // close with RST, not FIN
        setsockopt(connection, SOL_SOCKET, SO_LINGER, &reset, socklen_t(MemoryLayout<linger>.size))
        close(connection)
    }
}
