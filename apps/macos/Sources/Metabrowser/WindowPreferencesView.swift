import ShellCore
import SwiftUI

/// The window preferences in Settings, in the user defaults `WindowPreferences` reads.
struct WindowPreferencesView: View {
    @AppStorage(WindowPreferences.placementKey) private var placement = WindowPreferences.defaultPlacement
    @AppStorage(WindowPreferences.restoreKey) private var restoresLastSession =
        WindowPreferences.defaultRestoresLastSession

    var body: some View {
        Grid(alignment: .leadingFirstTextBaseline, horizontalSpacing: 12, verticalSpacing: 8) {
            GridRow {
                Text("Open folders in").foregroundStyle(.secondary)
                Picker("Open folders in", selection: $placement) {
                    Text("Tabs or windows, as System Settings prefers").tag(FolderPlacement.system)
                    Text("Tabs").tag(FolderPlacement.tabs)
                    Text("Windows").tag(FolderPlacement.windows)
                }
                .labelsHidden()
                .fixedSize()
            }
            GridRow {
                Color.clear.gridCellUnsizedAxes([.horizontal, .vertical])
                Toggle("Reopen the last session's folders when Metabrowser opens", isOn: $restoresLastSession)
            }
        }
    }
}
