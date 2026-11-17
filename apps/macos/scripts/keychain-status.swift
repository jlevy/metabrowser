// Reports a keychain's state for the signing doctor (scripts/check-signing.sh), which
// compiles and runs it, without unlocking the keychain or asking for anything: whether
// it exists, whether it is unlocked, its lock settings, and whether it holds the item
// notarytool saves for a profile. It turns keychain prompts off first, so a call that
// would need one fails with errSecInteractionNotAllowed instead of showing it.
//
//   swiftc -suppress-warnings -O scripts/keychain-status.swift -o keychain-status
//   keychain-status KEYCHAIN [PROFILE]
//
// It prints KEY=VALUE lines, which signing-lib.sh reads (status_value):
//   exists=0|1
//   unlocked=0|1, or unknown: REASON
//   lock_on_sleep=0|1, use_lock_interval=0|1, lock_interval=SECONDS; or
//     settings=unreadable: REASON when macOS will not show them
//   profile=found|absent, or unknown: REASON, when PROFILE is given
// and exits 0, or 1 with error=REASON when it cannot read the keychain at all.
//
// The SecKeychain calls are deprecated, and there is no replacement for a keychain file:
// SecItem calls cannot say whether one is locked or how it locks.
import Foundation
import Security

let arguments = CommandLine.arguments
guard arguments.count == 2 || arguments.count == 3 else {
    FileHandle.standardError.write(Data("usage: keychain-status KEYCHAIN [PROFILE]\n".utf8))
    exit(2)
}
let path = arguments[1]

func report(_ key: String, _ value: String) {
    print("\(key)=\(value)")
}

func reason(_ status: OSStatus) -> String {
    (SecCopyErrorMessageString(status, nil) as String?) ?? "OSStatus \(status)"
}

// Before any other keychain call, so that none of them can prompt.
let interaction = SecKeychainSetUserInteractionAllowed(false)
guard interaction == errSecSuccess else {
    report("error", "could not turn off keychain prompts: \(reason(interaction))")
    exit(1)
}

guard FileManager.default.fileExists(atPath: path) else {
    report("exists", "0")
    exit(0)
}
report("exists", "1")

var opened: SecKeychain?
let openStatus = SecKeychainOpen(path, &opened)
guard openStatus == errSecSuccess, let keychain = opened else {
    report("error", "could not open \(path): \(reason(openStatus))")
    exit(1)
}

var state: SecKeychainStatus = 0
let stateStatus = SecKeychainGetStatus(keychain, &state)
if stateStatus == errSecSuccess {
    report("unlocked", state & UInt32(kSecUnlockStateStatus) != 0 ? "1" : "0")
} else {
    report("unlocked", "unknown: \(reason(stateStatus))")
}

var settings = SecKeychainSettings(
    version: UInt32(SEC_KEYCHAIN_SETTINGS_VERS1), lockOnSleep: false, useLockInterval: false, lockInterval: 0)
let settingsStatus = SecKeychainCopySettings(keychain, &settings)
if settingsStatus == errSecSuccess {
    report("lock_on_sleep", settings.lockOnSleep.boolValue ? "1" : "0")
    report("use_lock_interval", settings.useLockInterval.boolValue ? "1" : "0")
    report("lock_interval", String(settings.lockInterval))
} else {
    report("settings", "unreadable: \(reason(settingsStatus))")
}

if arguments.count == 3 {
    // The item notarytool 1.1 saves for `store-credentials PROFILE`. Its names are not
    // documented, so a miss is reported as such, and the doctor's ONLINE=1 run, which
    // asks the notary service, is the check that the profile works.
    let query: [String: Any] = [
        kSecClass as String: kSecClassGenericPassword,
        kSecAttrService as String: "com.apple.gke.notary.tool",
        kSecAttrAccount as String: "com.apple.gke.notary.tool.saved-creds.\(arguments[2])",
        kSecMatchSearchList as String: [keychain],
        kSecMatchLimit as String: kSecMatchLimitOne,
        kSecReturnAttributes as String: true,
    ]
    var item: CFTypeRef?
    let itemStatus = SecItemCopyMatching(query as CFDictionary, &item)
    switch itemStatus {
    case errSecSuccess: report("profile", "found")
    case errSecItemNotFound: report("profile", "absent")
    default: report("profile", "unknown: \(reason(itemStatus))")
    }
}
