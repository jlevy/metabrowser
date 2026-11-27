import Foundation

let arguments = CommandLine.arguments.dropFirst()
guard let executable = arguments.first else {
    FileHandle.standardError.write(Data("Usage: HardenedLauncher EXECUTABLE [ARG ...]\n".utf8))
    exit(2)
}

let child = Process()
child.executableURL = URL(fileURLWithPath: executable)
child.arguments = Array(arguments.dropFirst())
try child.run()
child.waitUntilExit()
exit(child.terminationStatus)
