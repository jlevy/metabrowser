import AppKit

/// The menu bar, built in code. Items with a nil target travel the responder chain:
/// the key window's web view answers Cut, Copy, Paste, Select All, and Undo itself,
/// its window controller answers the page and server items, and the app delegate
/// answers the rest. Without an Edit menu, Command-C and Command-V do nothing in a web
/// view. A web view hands a key to its page before the menu, and the page binds plain
/// keys and, on a pull request in a stack, Control-N and Control-P, which no item here
/// uses; it takes no other key held with Command, Control, or Option, so every shortcut
/// here reaches the app (`tests/test_modified_keys.py` holds the page to that).
enum MainMenu {
    /// `appName` is the bundle's name, which the app menu's items carry.
    static func build(appName: String, recentFolders: NSMenuDelegate) -> NSMenu {
        let main = NSMenu()
        main.addSubmenu(appName, [
            item("About \(appName)", #selector(AppDelegate.showAbout(_:))),
            .separator(),
            item("Settings…", #selector(AppDelegate.showSettings(_:)), ","),
            item("Clear Website Data…", #selector(AppDelegate.clearWebsiteData(_:))),
            .separator(),
            item("Hide \(appName)", #selector(NSApplication.hide(_:)), "h"),
            item("Hide Others", #selector(NSApplication.hideOtherApplications(_:)), "h", [.command, .option]),
            item("Show All", #selector(NSApplication.unhideAllApplications(_:))),
            .separator(),
            item("Quit \(appName)", #selector(NSApplication.terminate(_:)), "q"),
        ])

        let recent = NSMenu(title: "Open Recent")
        recent.delegate = recentFolders
        let recentHolder = NSMenuItem(title: "Open Recent", action: nil, keyEquivalent: "")
        recentHolder.submenu = recent
        // Open Folder… opens a folder or a file in folder mode, and Open URL… a GitHub URL
        // in its mirror (docs/project/architecture/arch-open-modes.md, The File Menu).
        main.addSubmenu("File", [
            item("Open Folder…", #selector(AppDelegate.openFolder(_:)), "o"),
            item("Open URL…", #selector(AppDelegate.showOpenURL(_:)), "l"),
            recentHolder,
            .separator(),
            item("Close Window", #selector(NSWindow.performClose(_:)), "w"),
            item("Close Folder", #selector(BrowserWindowController.closeFolder(_:))),
            .separator(),
            item("Restart Server", #selector(FolderPage.restartServer(_:)), "r", [.command, .option]),
            item("Copy Current URL", #selector(FolderPage.copyCurrentURL(_:))),
            item("Open in Default Browser", #selector(FolderPage.openInDefaultBrowser(_:))),
            item("Reveal Server Log", #selector(FolderPage.revealServerLog(_:))),
            .separator(),
            item("Print…", #selector(FolderPage.printPage(_:)), "p"),
        ])

        let find = NSMenu(title: "Find")
        for (title, action, key, modifiers) in [
            ("Find…", NSTextFinder.Action.showFindInterface, "f", NSEvent.ModifierFlags.command),
            ("Find Next", .nextMatch, "g", .command),
            ("Find Previous", .previousMatch, "g", [.command, .shift]),
            ("Use Selection for Find", .setSearchString, "e", .command),
        ] {
            let findItem = item(title, #selector(FolderPage.performFindAction(_:)), key, modifiers)
            findItem.tag = action.rawValue
            find.addItem(findItem)
        }
        let findHolder = NSMenuItem(title: "Find", action: nil, keyEquivalent: "")
        findHolder.submenu = find
        main.addSubmenu("Edit", [
            item("Undo", Selector(("undo:")), "z"),
            item("Redo", Selector(("redo:")), "z", [.command, .shift]),
            .separator(),
            item("Cut", #selector(NSText.cut(_:)), "x"),
            item("Copy", #selector(NSText.copy(_:)), "c"),
            item("Paste", #selector(NSText.paste(_:)), "v"),
            item("Select All", #selector(NSText.selectAll(_:)), "a"),
            .separator(),
            findHolder,
        ])

        main.addSubmenu("View", [
            item("Switch Folder…", #selector(BrowserWindowController.switchFolder(_:)), "o", [.command, .shift]),
            .separator(),
            item("Back", #selector(FolderPage.navigateBack(_:)), "["),
            item("Forward", #selector(FolderPage.navigateForward(_:)), "]"),
            item("Back History", #selector(FolderPage.showBackHistory(_:))),
            item("Forward History", #selector(FolderPage.showForwardHistory(_:))),
            item("Reload Page", #selector(FolderPage.reloadPage(_:)), "r"),
            .separator(),
            item("Actual Size", #selector(FolderPage.actualSize(_:)), "0"),
            item("Zoom In", #selector(FolderPage.zoomIn(_:)), "="),
            item("Zoom Out", #selector(FolderPage.zoomOut(_:)), "-"),
            .separator(),
            item("Enter Full Screen", #selector(NSWindow.toggleFullScreen(_:)), "f", [.command, .control]),
        ])

        NSApp.windowsMenu = main.addSubmenu("Window", [
            item("Minimize", #selector(NSWindow.performMiniaturize(_:)), "m"),
            item("Zoom", #selector(NSWindow.performZoom(_:))),
            .separator(),
            item("Bring All to Front", #selector(NSApplication.arrangeInFront(_:))),
        ])
        NSApp.helpMenu = main.addSubmenu("Help", [
            item("Metabrowser Documentation", #selector(AppDelegate.openDocumentation(_:))),
            .separator(),
            item("Check Setup…", #selector(AppDelegate.showCheckSetup(_:))),
            item("Reveal Logs Folder", #selector(AppDelegate.revealLogsFolder(_:))),
            item("Open Event Log", #selector(AppDelegate.openEventLog(_:))),
        ])
        return main
    }

    /// A menu item, with its key equivalent's modifiers: the one place the app sets a
    /// modifier mask, which the folder chooser's items use too, so
    /// `tests/test_modified_keys.py` reads every one.
    static func item(
        _ title: String, _ action: Selector, _ key: String = "",
        _ modifiers: NSEvent.ModifierFlags = .command
    ) -> NSMenuItem {
        let menuItem = NSMenuItem(title: title, action: action, keyEquivalent: key)
        menuItem.keyEquivalentModifierMask = modifiers
        return menuItem
    }
}

extension NSMenu {
    @discardableResult
    fileprivate func addSubmenu(_ title: String, _ items: [NSMenuItem]) -> NSMenu {
        let submenu = NSMenu(title: title)
        items.forEach(submenu.addItem)
        let holder = NSMenuItem(title: title, action: nil, keyEquivalent: "")
        holder.submenu = submenu
        addItem(holder)
        return submenu
    }
}
