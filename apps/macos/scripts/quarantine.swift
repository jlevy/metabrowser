// Quarantines a file the way a download is, through the supported interface,
// URLResourceKey.quarantinePropertiesKey, when it has no quarantine attribute already.
// It is a simulation of a browser download for scripts/check-release.sh: `gh release
// download` does not quarantine what it downloads, and a browser does. Apple DTS says
// the attribute's on-disk format is not API, so this does not write it directly.
//
//   swiftc -O scripts/quarantine.swift -o quarantine
//   quarantine FILE
//
// Prints "already" when the file was quarantined, or "simulated" when this quarantined
// it, and exits 1 with the reason when it cannot.
import CoreServices
import Foundation

guard CommandLine.arguments.count == 2 else {
    FileHandle.standardError.write(Data("usage: quarantine FILE\n".utf8))
    exit(2)
}
var url = URL(fileURLWithPath: CommandLine.arguments[1])

do {
    if try url.resourceValues(forKeys: [.quarantinePropertiesKey]).quarantineProperties != nil {
        print("already")
        exit(0)
    }
    var values = URLResourceValues()
    values.quarantineProperties = [
        kLSQuarantineAgentNameKey as String: "Metabrowser check-release (simulated download)",
        kLSQuarantineTypeKey as String: kLSQuarantineTypeWebDownload as String,
    ]
    try url.setResourceValues(values)
    print("simulated")
} catch {
    FileHandle.standardError.write(Data("could not quarantine \(url.path): \(error)\n".utf8))
    exit(1)
}
