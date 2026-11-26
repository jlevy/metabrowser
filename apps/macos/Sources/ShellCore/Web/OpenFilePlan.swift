import Darwin
import Foundation
import UniformTypeIdentifiers

/// Why a page's Open link opened nothing.
public nonisolated struct OpenFileFailure: Error, Equatable, Sendable {
    /// The file's name, as the link gives it.
    public var name: String
    public var reason: String
    /// A file on disk that the alert offers to show in Finder, for a type the app does not
    /// open (`OpenFileTypes`).
    public var reveal: URL?

    public init(name: String, reason: String, reveal: URL? = nil) {
        self.name = name
        self.reason = reason
        self.reveal = reveal
    }

    /// One sentence for an alert, as `DownloadFailure.message` words a download's.
    public var message: String {
        let because = reason.hasSuffix(".") ? String(reason.dropLast()) : reason
        return "Could not open “\(name)”: \(because)."
    }
}

/// What a window does with a click on a page's Open link (`OpenFileRequests.Request`),
/// decided from what the window serves (`SessionRoot`), which only the app knows: whether
/// the path is a file on this disk, or bytes of a pinned revision or a mirror, which only
/// the server can answer.
public nonisolated enum OpenFilePlan: Equatable, Sendable {
    /// Open the file itself, at its real path inside the folder.
    case openFile(URL)
    /// Download the link's bytes to a read-only copy of `name` and open that
    /// (`OpenFileDownloads`).
    case downloadThenOpen(URL, name: String)
    case refuse(OpenFileFailure)

    /// - A `filesystem` path in a folder's window is the file at that path under the
    ///   folder: the path is relative, with no `.`, `..`, or empty part, and its real path,
    ///   with every symbolic link resolved, must be a regular file inside the folder's real
    ///   path, so no link in the folder opens a file outside it.
    /// - A `git_revision` path, or any path in a repository's window, which has no folder
    ///   on disk, is downloaded from the link. A name that gives no type the system knows,
    ///   such as one with no extension, is downloaded too, and its copy is named by the
    ///   type it is served as (`OpenFileTypes.copyName`).
    /// - A file whose type `OpenFileTypes` does not allow is refused; one on disk is
    ///   offered to Finder instead.
    public static func resolve(_ request: OpenFileRequests.Request, in root: SessionRoot) -> OpenFilePlan {
        guard case .folder(let folder) = root, request.subject == .filesystem else {
            guard !OpenFileTypes.refusesBeforeDownload(request.name) else {
                return .refuse(OpenFileFailure(name: request.name, reason: OpenFileTypes.refusal))
            }
            return .downloadThenOpen(request.href, name: request.name)
        }
        return file(request.path, in: folder, named: request.name)
    }

    /// The plan for a `filesystem` path relative to `folder`.
    static func file(_ relative: String, in folder: URL, named name: String) -> OpenFilePlan {
        func refuse(_ reason: String, reveal: URL? = nil) -> OpenFilePlan {
            .refuse(OpenFileFailure(name: name, reason: reason, reveal: reveal))
        }
        let parts = relative.split(separator: "/", omittingEmptySubsequences: false)
        guard !relative.hasPrefix("/"), !parts.contains(where: { $0.isEmpty || $0 == "." || $0 == ".." }) else {
            return refuse("its path does not name a file in this folder")
        }
        let root = FileChecks.canonicalPath(folder.path(percentEncoded: false))
        let real = FileChecks.canonicalPath(root + (root.hasSuffix("/") ? "" : "/") + relative)
        var info = stat()
        guard stat(real, &info) == 0 else { return refuse("it is not in this folder any more") }
        guard OpenTarget.contains(root, real) else { return refuse("it is a link to a file outside this folder") }
        let file = URL(filePath: real, directoryHint: .notDirectory)
        guard info.st_mode & S_IFMT == S_IFREG else { return refuse("it is not a file") }
        guard OpenFileTypes.allows(OpenFileTypes.type(of: file)) else {
            return refuse(OpenFileTypes.refusal, reveal: file)
        }
        return .openFile(file)
    }
}

/// Which files a page's Open link may open in their default app.
public nonisolated enum OpenFileTypes {
    /// Documents and media, whose default handlers show them. The default handler of a
    /// script, an application, an installer package, a disk image, or an internet
    /// location runs or mounts something, and a page's link should never do that, so
    /// every type that conforms to none of these is refused. A plugin that marks another
    /// kind of file widens this list.
    public static let allowed: [UTType] = [.pdf, .image, .audiovisualContent]
    /// Refused although an allowed type covers it: an SVG image is a document that runs
    /// scripts, and its default handler is often a web browser, which runs them.
    public static let excluded: [UTType] = [.svg]

    /// The reason an alert gives for a type that is not allowed.
    static let refusal = "Metabrowser opens only PDF documents, images, audio, and video in their default app"

    public static func allows(_ type: UTType?) -> Bool {
        guard let type else { return false }
        return allowed.contains { type.conforms(to: $0) } && !excluded.contains { type.conforms(to: $0) }
    }

    /// A file's type as Launch Services reads it (`contentTypeKey`), else by its extension.
    public static func type(of file: URL) -> UTType? {
        (try? file.resourceValues(forKeys: [.contentTypeKey]))?.contentType ?? type(named: file.lastPathComponent)
    }

    /// The type a file named `name` would have, by its extension, or nil for none.
    public static func type(named name: String) -> UTType? {
        let pathExtension = (name as NSString).pathExtension
        return pathExtension.isEmpty ? nil : UTType(filenameExtension: pathExtension)
    }

    /// `type`, or nil when the system knows nothing of it: a dynamic type is what an
    /// extension or a media type that no app declares gives, and it conforms to nothing.
    static func known(_ type: UTType?) -> UTType? {
        guard let type, !type.isDynamic else { return nil }
        return type
    }

    /// Whether a copy named `name` is refused before anything downloads: its name gives a
    /// type the system knows, and the app does not open it. A name that gives none, with
    /// no extension or one no app declares, is downloaded, and its copy is judged by the
    /// name it is kept under, which the type it is served as can give (`copyName`).
    static func refusesBeforeDownload(_ name: String) -> Bool {
        guard let type = known(type(named: name)) else { return false }
        return !allows(type)
    }

    /// The name a downloaded copy of `name` is kept under, given the media type the server
    /// answered with (`Content-Type`, as `URLResponse.mimeType` reads it):
    ///
    /// - `name`, when the media type gives no type the system knows, such as
    ///   `application/octet-stream` or none; when its type is one `allows` refuses, so a
    ///   served type never names a copy a script, a page, or an application; or when the
    ///   name agrees with it: its type conforms to the served one or the served one to
    ///   it, as a `.m4a` does to `audio/mp4`, or its extension is one of the served
    ///   type's, as `.mp4` is of `audio/mp4`, a type `.mp4` itself does not conform to.
    /// - Otherwise `name` and the media type's preferred extension, so a PDF with no
    ///   extension, which `/raw` serves as `application/pdf`, is kept as `name.pdf` and
    ///   opens in the PDF app, and a `photo.png` served as JPEG as `photo.png.jpeg`. The
    ///   name is cut to fit a file name (`NAME_MAX` bytes).
    ///
    /// The copy is checked by the name it is kept under, as every copy is
    /// (`OpenFileDownloads`), so a served type renames a copy only to a type `allows`,
    /// and only that check decides whether it opens.
    public static func copyName(_ name: String, servedAs mediaType: String?) -> String {
        guard let served = known(mediaType.flatMap { UTType(mimeType: $0) }), allows(served),
              let pathExtension = served.preferredFilenameExtension
        else { return name }
        if let own = known(type(named: name)), own.conforms(to: served) || served.conforms(to: own) {
            return name
        }
        let ownExtension = (name as NSString).pathExtension.lowercased()
        if !ownExtension.isEmpty, served.tags[.filenameExtension]?.contains(ownExtension) == true {
            return name
        }
        return fitted(name, "." + pathExtension)
    }

    /// `stem` and then `suffix`, with as many characters cut from the end of `stem` as a
    /// file name of at most `NAME_MAX` bytes needs.
    static func fitted(_ stem: String, _ suffix: String) -> String {
        var stem = stem
        while !stem.isEmpty, stem.utf8.count + suffix.utf8.count > Int(NAME_MAX) {
            stem.removeLast()
        }
        return stem + suffix
    }
}
