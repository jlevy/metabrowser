import Foundation

/// Polls a loopback URL for a 2xx.
public nonisolated enum HTTPReadiness {
    /// One probe's limit, in seconds. A loopback server that is listening answers far
    /// sooner; the caller's deadline bounds the whole wait.
    static let requestTimeout: TimeInterval = 2

    /// Ephemeral, uncached, and never routed through a system proxy.
    private static let session: URLSession = {
        let configuration = URLSessionConfiguration.ephemeral
        configuration.connectionProxyDictionary = [:]
        configuration.timeoutIntervalForRequest = requestTimeout
        configuration.requestCachePolicy = .reloadIgnoringLocalCacheData
        configuration.httpShouldSetCookies = false
        return URLSession(configuration: configuration)
    }()

    /// True when `url` answers with a 2xx. Connection refused, timeouts, and every
    /// other status count as not ready yet.
    public static let probe: @Sendable (URL) async -> Bool = { url in
        guard let (_, response) = try? await session.data(from: url),
              let http = response as? HTTPURLResponse
        else { return false }
        return (200..<300).contains(http.statusCode)
    }
}
