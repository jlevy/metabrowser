import Foundation
import os

/// Resolves once with a value; any number of callers may await it. A waiter whose task
/// is cancelled gets nil, which is what lets a timeout race finish: `withTaskGroup`
/// does not return until every child task has returned.
public nonisolated final class Latch<Value: Sendable>: Sendable {
    private typealias Waiter = CheckedContinuation<Value?, Never>
    private struct State {
        var value: Value?
        var waiters: [UUID: Waiter] = [:]
    }
    private let state = OSAllocatedUnfairLock(initialState: State())

    public init() {}

    public var isResolved: Bool { state.withLock { $0.value != nil } }

    public func resolve(_ value: Value) {
        let waiters = state.withLock { s -> [Waiter] in
            guard s.value == nil else { return [] }
            s.value = value
            defer { s.waiters = [:] }
            return Array(s.waiters.values)
        }
        waiters.forEach { $0.resume(returning: value) }
    }

    public func wait() async -> Value? {
        let id = UUID()
        return await withTaskCancellationHandler {
            await withCheckedContinuation { (waiter: Waiter) in
                let immediate: Value?? = state.withLock { s in
                    if let value = s.value { return .some(value) }
                    if Task.isCancelled { return .some(nil) }
                    s.waiters[id] = waiter
                    return .none
                }
                if let immediate { waiter.resume(returning: immediate) }
            }
        } onCancel: {
            state.withLock { $0.waiters.removeValue(forKey: id) }?.resume(returning: nil)
        }
    }
}

/// Splits a byte stream into lines. Used from one serial reader only.
nonisolated final class LineSplitter: @unchecked Sendable {
    private var pending = [UInt8]()

    func append(_ bytes: some Sequence<UInt8>, emit: (String) -> Void) {
        pending.append(contentsOf: bytes)
        while let newline = pending.firstIndex(of: 0x0A) {
            var line = pending[..<newline]
            if line.last == 0x0D { line = line.dropLast() }
            emit(String(decoding: line, as: UTF8.self))
            pending.removeSubrange(...newline)
        }
    }

    /// The unterminated last line, if the stream ended without a newline.
    func finish(emit: (String) -> Void) {
        guard !pending.isEmpty else { return }
        emit(String(decoding: pending, as: UTF8.self))
        pending.removeAll()
    }
}

/// The newest output lines of a child, kept for the error view.
public nonisolated final class OutputTail: Sendable {
    private let limit: Int
    private let lines = OSAllocatedUnfairLock(initialState: [String]())

    public init(limit: Int) { self.limit = max(1, limit) }

    public func append(_ line: String) {
        lines.withLock {
            $0.append(line)
            if $0.count > limit { $0.removeFirst($0.count - limit) }
        }
    }

    public var snapshot: [String] { lines.withLock { $0 } }
}

/// A `waitpid` status, decoded. Swift cannot call the `WIFEXITED` family of macros.
public nonisolated enum ExitStatus: Equatable, Sendable, CustomStringConvertible {
    case exited(Int32)
    case signaled(Int32)

    public init(waitStatus: Int32) {
        let signal = waitStatus & 0x7f
        self = signal == 0 ? .exited((waitStatus >> 8) & 0xff) : .signaled(signal)
    }

    public var description: String {
        switch self {
        case .exited(let code): "exit status \(code)"
        case .signaled(let signal): "signal \(signal) (\(Self.name(of: signal)))"
        }
    }

    static func name(of signal: Int32) -> String {
        switch signal {
        case SIGHUP: "SIGHUP"
        case SIGINT: "SIGINT"
        case SIGKILL: "SIGKILL"
        case SIGTERM: "SIGTERM"
        case SIGSEGV: "SIGSEGV"
        case SIGABRT: "SIGABRT"
        case SIGBUS: "SIGBUS"
        default: String(cString: strsignal(signal))
        }
    }
}
