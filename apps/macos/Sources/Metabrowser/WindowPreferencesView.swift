import ShellCore
import SwiftUI

/// Settings > General: the window preferences, in the user defaults `WindowPreferences` reads.
struct WindowPreferencesView: View {
    @AppStorage(WindowPreferences.restoreKey) private var restoresLastSession =
        WindowPreferences.defaultRestoresLastSession

    var body: some View {
        Toggle("Reopen the last session's folders when Metabrowser opens", isOn: $restoresLastSession)
    }
}
